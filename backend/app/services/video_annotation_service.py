"""Track correction and frame-accurate human annotation workflows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence
from uuid import uuid4

from backend.app.domain.errors import VideoResourceNotFoundError, VideoValidationError
from backend.app.domain.video import HUMAN_LABELS
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository


@dataclass(frozen=True)
class StagedPoseTrackRewrite:
    """One immutable pose artifact and the pointer it was derived from."""

    expected_version: str
    staged_version: str


class VideoAnnotationService:
    """Own validation, history, approval, and selective invalidation rules."""

    def __init__(self, repository: VideoRepository, storage: VideoStorageRepository) -> None:
        self.repository = repository
        self.storage = storage

    def save_segment(
        self,
        video_id: str,
        track_id: int,
        start_frame: int,
        end_frame: int,
        label: str,
        expected_revision: int,
        segment_id: str | None = None,
        source_type: str = "manual",
        source_id: str | None = None,
        *,
        emit_event: bool = True,
        schedule_derivatives: bool = True,
    ) -> dict[str, Any]:
        self._validate_segment(video_id, track_id, start_frame, end_frame, label, segment_id)
        segment, revision = self.repository.write_segment(
            video_id,
            {
                "track_id": track_id,
                "start_frame": start_frame,
                "end_frame": end_frame,
                "label": label,
                "source_type": source_type,
                "source_id": source_id,
                "quality_status": "good",
                "include_in_export": 1,
                "exclude_reason": None,
            },
            expected_revision,
            segment_id,
            emit_event=emit_event,
            schedule_derivatives=schedule_derivatives,
        )
        return {"segment": segment, "revision": revision}

    def list_tracks(self, video_id: str) -> list[dict[str, Any]]:
        return self.repository.list_tracks(video_id)

    def segment_snapshot(self, video_id: str, track_id: int | None = None) -> dict[str, Any]:
        video = self.repository.get_video(video_id)
        return {"revision": video["annotation_revision"], "segments": self.repository.list_segments(video_id, track_id)}

    def history(self, video_id: str) -> list[dict[str, Any]]:
        return self.repository.list_history(video_id)

    def materialize_suggestions(
        self,
        video_id: str,
        source: str,
        *,
        expected_revision: int | None = None,
    ) -> list[dict[str, Any]]:
        """Create editable ground-truth segments from a new suggestion set.

        Automatic materialization is intentionally limited to an unlabeled video.
        It gives newly imported videos an editable first pass while ensuring a
        later regeneration never replaces a reviewer's existing annotations.
        """
        if source not in {"threshold", "model"}:
            raise VideoValidationError("Suggestion source must be threshold or model")
        table = "threshold_suggestions" if source == "threshold" else "model_suggestions"
        candidates = [
            suggestion for suggestion in self.repository.list_suggestions(table, video_id)
            if suggestion["review_status"] == "pending"
        ]
        selected: list[dict[str, Any]] = []
        for suggestion in sorted(candidates, key=lambda item: (-float(item["confidence"]), int(item["start_frame"]))):
            overlaps = any(
                int(suggestion["track_id"]) == int(current["track_id"])
                and int(suggestion["start_frame"]) <= int(current["end_frame"])
                and int(suggestion["end_frame"]) >= int(current["start_frame"])
                for current in selected
            )
            if not overlaps:
                selected.append(suggestion)

        segments_to_create: list[dict[str, Any]] = []
        selected_by_track: dict[int, list[dict[str, Any]]] = {}
        for suggestion in selected:
            selected_by_track.setdefault(int(suggestion["track_id"]), []).append(suggestion)
        for track in self.repository.list_tracks(video_id):
            track_id = int(track["track_id"])
            cursor = int(track["start_frame"])
            for suggestion in sorted(selected_by_track.get(track_id, []), key=lambda item: int(item["start_frame"])):
                start_frame = int(suggestion["start_frame"])
                end_frame = int(suggestion["end_frame"])
                if cursor < start_frame:
                    segments_to_create.append({
                        "track_id": track_id, "start_frame": cursor,
                        "end_frame": start_frame - 1, "label": "others",
                        "source_type": "auto_default", "source_id": None,
                    })
                segments_to_create.append({
                    "track_id": track_id, "start_frame": start_frame,
                    "end_frame": end_frame, "label": suggestion["suggested_label"],
                    "source_type": source, "source_id": str(suggestion["suggestion_id"]),
                })
                cursor = end_frame + 1
            if cursor <= int(track["end_frame"]):
                segments_to_create.append({
                    "track_id": track_id, "start_frame": cursor,
                    "end_frame": int(track["end_frame"]), "label": "others",
                    "source_type": "auto_default", "source_id": None,
                })

        return self.repository.materialize_suggestion_segments(
            video_id,
            table,
            [str(suggestion["suggestion_id"]) for suggestion in selected],
            segments_to_create,
            expected_revision=expected_revision,
        )

    def delete_segment(
        self,
        video_id: str,
        segment_id: str,
        expected_revision: int,
        *,
        schedule_derivatives: bool = True,
    ) -> int:
        """Delete one segment and persist its derivative refresh intent."""

        return self.repository.delete_segment(
            video_id,
            segment_id,
            expected_revision,
            schedule_derivatives=schedule_derivatives,
        )

    def set_segment_inclusion(
        self, video_id: str, segment_id: str, include: bool, reason: str | None, expected_revision: int
    ) -> dict[str, Any]:
        if not include and not reason:
            raise VideoValidationError("An exclusion reason is required")
        segment = next((item for item in self.repository.list_segments(video_id) if item["segment_id"] == segment_id), None)
        if segment is None:
            raise VideoResourceNotFoundError("Segment not found")
        updated, revision = self.repository.write_segment(
            video_id,
            {
                "track_id": segment["track_id"], "start_frame": segment["start_frame"],
                "end_frame": segment["end_frame"], "label": segment["label"],
                "source_type": segment["source_type"], "source_id": segment["source_id"],
                "quality_status": "good" if include else "excluded", "include_in_export": int(include),
                "exclude_reason": None if include else reason,
            },
            expected_revision,
            segment_id,
        )
        return {"segment": updated, "revision": revision}

    def undo(self, video_id: str, expected_revision: int) -> int:
        return self.repository.undo_or_redo(video_id, expected_revision, "undo")

    def redo(self, video_id: str, expected_revision: int) -> int:
        return self.repository.undo_or_redo(video_id, expected_revision, "redo")

    def extend_segment(self, video_id: str, segment_id: str, expected_revision: int) -> dict[str, Any]:
        segments = self.repository.list_segments(video_id)
        segment = next((item for item in segments if item["segment_id"] == segment_id), None)
        if segment is None:
            raise VideoResourceNotFoundError("Segment not found")
        track = self.repository.get_track(video_id, int(segment["track_id"]))
        track_segments = sorted(
            (item for item in segments if int(item["track_id"]) == int(segment["track_id"]) and item["segment_id"] != segment_id),
            key=lambda item: int(item["start_frame"]),
        )
        preceding = [item for item in track_segments if int(item["end_frame"]) < int(segment["start_frame"])]
        previous = preceding[-1] if preceding else None
        next_segment = next((item for item in track_segments if int(item["start_frame"]) > int(segment["end_frame"])), None)
        start_frame = int(previous["end_frame"]) + 1 if previous else int(track["start_frame"])
        end_frame = int(next_segment["start_frame"]) - 1 if next_segment else int(track["end_frame"])
        if start_frame == int(segment["start_frame"]) and end_frame == int(segment["end_frame"]):
            return {"segment": segment, "revision": int(self.repository.get_video(video_id)["annotation_revision"])}
        return self.save_segment(
            video_id, int(segment["track_id"]), start_frame, end_frame,
            segment["label"], expected_revision, segment_id,
        )

    def copy_previous_label(
        self, video_id: str, track_id: int, start_frame: int, end_frame: int, expected_revision: int
    ) -> dict[str, Any]:
        previous = [item for item in self.repository.list_segments(video_id, track_id) if int(item["end_frame"]) < start_frame]
        if not previous:
            raise VideoValidationError("No previous segment label is available")
        label = max(previous, key=lambda item: item["end_frame"])["label"]
        return self.save_segment(video_id, track_id, start_frame, end_frame, label, expected_revision)

    def label_full_track(self, video_id: str, track_id: int, label: str, expected_revision: int) -> dict[str, Any]:
        track = self.repository.get_track(video_id, track_id)
        return self.save_segment(
            video_id, track_id, int(track["start_frame"]), int(track["end_frame"]), label, expected_revision
        )

    def split_segment(self, video_id: str, segment_id: str, frame: int, expected_revision: int) -> list[dict[str, Any]]:
        segment = next(
            (item for item in self.repository.list_segments(video_id) if item["segment_id"] == segment_id), None
        )
        if segment is None:
            raise VideoResourceNotFoundError("Segment not found")
        if not int(segment["start_frame"]) <= frame < int(segment["end_frame"]):
            raise VideoValidationError("Split frame must be inside the segment")
        first = self.save_segment(
            video_id, int(segment["track_id"]), int(segment["start_frame"]), frame,
            segment["label"], expected_revision, segment_id,
        )
        second = self.save_segment(
            video_id, int(segment["track_id"]), frame + 1, int(segment["end_frame"]),
            segment["label"], first["revision"],
        )
        return [first["segment"], second["segment"]]

    def merge_segments(self, video_id: str, segment_ids: list[str], expected_revision: int) -> dict[str, Any]:
        selected = [item for item in self.repository.list_segments(video_id) if item["segment_id"] in segment_ids]
        if len(selected) < 2:
            raise VideoValidationError("Select at least two segments to merge")
        if len({(item["track_id"], item["label"]) for item in selected}) != 1:
            raise VideoValidationError("Only same-label segments on one track can be merged")
        ordered = sorted(selected, key=lambda item: item["start_frame"])
        if any(int(right["start_frame"]) > int(left["end_frame"]) + 1 for left, right in zip(ordered, ordered[1:], strict=False)):
            raise VideoValidationError("Segments must be adjacent or overlapping")
        revision = expected_revision
        keeper = ordered[0]
        for item in ordered[1:]:
            revision = self.repository.delete_segment(video_id, item["segment_id"], revision)
        return self.save_segment(
            video_id, int(keeper["track_id"]), int(keeper["start_frame"]),
            max(int(item["end_frame"]) for item in ordered), keeper["label"], revision, keeper["segment_id"],
        )

    def approve(self, video_id: str) -> dict[str, Any]:
        """Mark the video as approved after validation.

        Raises VideoValidationError if any segment is invalid or if no segments exist.
        """
        video = self.repository.get_video(video_id)
        errors = self.validate_video(video_id)
        if errors:
            raise VideoValidationError("Cannot approve video: " + "; ".join(errors))
        return self.repository.update_video(
            video_id,
            is_approved=1,
            approval_revision=video["annotation_revision"],
            approved_at=self.repository.one("SELECT CURRENT_TIMESTAMP AS value")["value"],
            annotation_status="approved",
        )

    def unapprove(self, video_id: str) -> dict[str, Any]:
        """Revoke approval so annotations can be revised.

        Resets is_approved to 0 and annotation_status back to 'labeled'.
        """
        segments = self.repository.list_segments(video_id)
        status = "labeled" if segments else "unlabeled"
        return self.repository.update_video(
            video_id,
            is_approved=0,
            annotation_status=status,
        )

    def validate_video(self, video_id: str) -> list[str]:
        errors: list[str] = []
        segments = self.repository.list_segments(video_id)
        tracks = self.repository.list_tracks(video_id, include_excluded=False)
        
        if not tracks:
            errors.append("no worker tracks detected. Process the video first.")
        elif not segments:
            errors.append("no segments have been labeled for this video.")
            
        for segment in segments:
            try:
                self._validate_segment(
                    video_id, int(segment["track_id"]), int(segment["start_frame"]),
                    int(segment["end_frame"]), segment["label"], segment["segment_id"],
                )
            except VideoValidationError as exc:
                errors.append(f"{segment['segment_id']}: {exc}")
        return errors

    def merge_tracks(
        self,
        video_id: str,
        target_track_id: int,
        source_track_id: int,
    ) -> dict[str, Any]:
        """Merge two workers through one durable database mutation."""

        if target_track_id == source_track_id:
            raise VideoValidationError("Choose two different tracks")
        staged_pose = self._stage_pose_track_rewrites(
            video_id,
            [(source_track_id, target_track_id, 0)],
        )
        return self.repository.merge_tracks_atomically(
            video_id,
            target_track_id,
            source_track_id,
            pose_cache_version=(staged_pose.staged_version if staged_pose else None),
            expected_pose_cache_version=(
                staged_pose.expected_version if staged_pose else None
            ),
        )

    def merge_multiple_tracks(self, video_id: str, track_ids: list[int]) -> dict[str, Any]:
        """Merge all listed tracks into the first track ID in the list.

        Iterates pairwise, merging each subsequent track into the target.
        Returns the final merged track.
        """
        if len(track_ids) < 2 or len(set(track_ids)) != len(track_ids):
            raise VideoValidationError("At least two track IDs are required for a multi-merge")
        target_id = track_ids[0]
        staged_pose = self._stage_pose_track_rewrites(
            video_id,
            [(source_id, target_id, 0) for source_id in track_ids[1:]],
        )
        return self.repository.merge_multiple_tracks_atomically(
            video_id,
            track_ids,
            pose_cache_version=(staged_pose.staged_version if staged_pose else None),
            expected_pose_cache_version=(
                staged_pose.expected_version if staged_pose else None
            ),
        )

    def split_track(self, video_id: str, track_id: int, frame: int) -> list[dict[str, Any]]:
        track = self.repository.get_track(video_id, track_id)
        if not int(track["start_frame"]) < frame <= int(track["end_frame"]):
            raise VideoValidationError("Track split frame must be inside its lifespan")
        new_id = max(
            (item["track_id"] for item in self.repository.list_tracks(video_id)),
            default=0,
        ) + 1
        staged_pose = self._stage_pose_track_rewrites(
            video_id,
            [(track_id, new_id, frame)],
        )
        return self.repository.split_track_atomically(
            video_id,
            track_id,
            frame,
            new_track_id=new_id,
            pose_cache_version=(staged_pose.staged_version if staged_pose else None),
            expected_pose_cache_version=(
                staged_pose.expected_version if staged_pose else None
            ),
        )

    def reassign_segment(self, video_id: str, segment_id: str, target_track_id: int, expected_revision: int) -> dict[str, Any]:
        segment = next((item for item in self.repository.list_segments(video_id) if item["segment_id"] == segment_id), None)
        if segment is None:
            raise VideoResourceNotFoundError("Segment not found")
        return self.save_segment(
            video_id, target_track_id, int(segment["start_frame"]), int(segment["end_frame"]),
            segment["label"], expected_revision, segment_id,
        )

    def set_track_inclusion(self, video_id: str, track_id: int, include: bool, reason: str | None) -> dict[str, Any]:
        if not include and not reason:
            raise VideoValidationError("An exclusion reason is required")
        track = self.repository.set_track_inclusion_atomically(
            video_id,
            track_id,
            include,
            reason,
        )
        return track

    def delete_track(self, video_id: str, track_id: int) -> dict[str, Any]:
        """Delete a worker track and all its segments."""
        self.repository.delete_track_atomically(video_id, track_id)
        return {"status": "success"}

    def _validate_segment(
        self, video_id: str, track_id: int, start_frame: int, end_frame: int,
        label: str, segment_id: str | None,
    ) -> None:
        if label not in HUMAN_LABELS:
            raise VideoValidationError("Human label must be others, running, or falling")
        video = self.repository.get_video(video_id)
        track = self.repository.get_track(video_id, track_id)
        if start_frame < 0 or end_frame < start_frame or end_frame >= int(video["canonical_frame_count"]):
            raise VideoValidationError("Segment range is outside video bounds")
        if start_frame < int(track["start_frame"]) or end_frame > int(track["end_frame"]):
            raise VideoValidationError("Segment range is outside track lifespan")
        for existing in self.repository.list_segments(video_id, track_id):
            if existing["segment_id"] != segment_id and start_frame <= int(existing["end_frame"]) and end_frame >= int(existing["start_frame"]):
                raise VideoValidationError("This segment conflicts with another segment.")

    def _stage_pose_track_rewrites(
        self,
        video_id: str,
        rewrites: Sequence[tuple[int, int, int]],
    ) -> StagedPoseTrackRewrite | None:
        """Publish a new immutable pose artifact for a pending track edit.

        The old artifact is never overwritten. The caller passes the returned
        version to its locked repository mutation, which switches
        ``videos.pose_cache_version`` in that same SQLite commit as tracks,
        revision, derivative intent, and outbox events. A process crash before
        commit therefore leaves the old pointer authoritative and the new file
        as harmless unreferenced staging data.
        """

        video = self.repository.get_video(video_id)
        version = video.get("pose_cache_version")
        if not version or not rewrites:
            return None
        source_path = self.storage.artifact_path(
            str(video["project_id"]),
            "pose",
            video_id,
            str(version),
        )
        if not source_path.is_file():
            # Track corrections remain useful after an interrupted cache
            # cleanup. The revision-pinned derivative job will rebuild its
            # dependants; a missing pose artifact must not block the edit.
            return None
        try:
            original = self.storage.read_json(source_path)
        except (OSError, ValueError, EOFError, VideoResourceNotFoundError):
            # Keep historical tolerant behavior for damaged pose caches. The
            # database mutation still invalidates all stale derivatives.
            return None
        # The source artifact stays on disk untouched, so rewriting its loaded
        # in-memory value does not need a second full pose-data copy.
        rewritten = original
        for old_id, new_id, from_frame in rewrites:
            for frame in rewritten.get("frames", []):
                if int(frame["frame_index"]) < from_frame:
                    continue
                for detection in frame.get("tracks", []):
                    if int(detection["track_id"]) == old_id:
                        detection["track_id"] = new_id
        staged_version = f"{version}-track-edit-{uuid4().hex[:12]}"
        staged_path = self.storage.artifact_path(
            str(video["project_id"]),
            "pose",
            video_id,
            staged_version,
        )
        self.storage.write_json(staged_path, rewritten)
        return StagedPoseTrackRewrite(
            expected_version=str(version),
            staged_version=staged_version,
        )
