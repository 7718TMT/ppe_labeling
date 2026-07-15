"""Project, import, queue, and track workflows for pose-video labeling."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sqlite3
import subprocess
import tempfile
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

import cv2
import numpy as np
from imageio_ffmpeg import get_ffmpeg_exe

from backend.app.domain.errors import (
    DuplicateVideoError,
    ModelCompatibilityError,
    VideoResourceNotFoundError,
    VideoValidationError,
)
from backend.app.domain.video import (
    FEATURE_SCHEMA_VERSION,
    TRACKING_CACHE_VERSION,
    WINDOW_CONFIG_VERSION,
    WINDOW_LENGTH_FRAMES,
    canonical_frame_mapping,
    project_config,
    threshold_profile_config,
    validate_project_config,
)
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository


VIDEO_MEDIA_TYPES = {
    ".avi": "video/x-msvideo",
    ".m4v": "video/mp4",
    ".mkv": "video/x-matroska",
    ".mov": "video/quicktime",
    ".mp4": "video/mp4",
    ".webm": "video/webm",
}
THUMBNAIL_WIDTH = 320
THUMBNAIL_HEIGHT = 180


class VideoService:
    """Coordinate project/video lifecycle without image-workflow coupling."""

    def __init__(self, repository: VideoRepository, storage: VideoStorageRepository) -> None:
        self.repository = repository
        self.storage = storage

    def create_project(self, name: str, config: dict[str, Any] | None = None) -> dict[str, Any]:
        clean_name = name.strip()
        if not clean_name:
            raise VideoValidationError("Project name is required")
        final_config = config or project_config()
        validate_project_config(final_config)
        project = self.repository.create_project(clean_name, final_config, "0.2.0")
        self.storage.ensure_project(project["project_id"])
        profile = self.repository.create_threshold_profile(
            project["project_id"], "Default", "v1", threshold_profile_config(), is_default=True
        )
        project["active_threshold_profile_id"] = profile["threshold_profile_id"]
        return self.repository.get_project(project["project_id"])

    def list_projects(self) -> list[dict[str, Any]]:
        return self.repository.list_projects()

    def get_project(self, project_id: str) -> dict[str, Any]:
        result = self.repository.get_project(project_id)
        result["workspace_state"] = self.repository.workspace_state(project_id)
        return result

    def list_videos(self, project_id: str, status: str | None = None) -> list[dict[str, Any]]:
        return self.repository.list_videos(project_id, status)

    def get_video(self, project_id: str, video_id: str) -> dict[str, Any]:
        video = self._project_video(project_id, video_id)
        video["frame_mapping"] = self.repository.frame_mapping(video_id)
        return video

    def media_path(self, project_id: str, video_id: str) -> Path:
        """Return the owned raw import used by browser playback.

        Canonical MPEG-4 caches are intentionally worker-only. Some OpenCV
        builds encode them as FMP4, which is valid for pose processing but is
        not reliably playable by browsers. Frame synchronization remains based
        on canonical timestamps, so serving the untouched raw media is safe.
        """

        return self.media(project_id, video_id)[0]

    def media(self, project_id: str, video_id: str) -> tuple[Path, str]:
        """Return the browser media path and its suffix-specific content type."""

        video = self._project_video(project_id, video_id)
        path = self.storage.raw_path(project_id, video["relative_path"])
        return path, VIDEO_MEDIA_TYPES.get(path.suffix.lower(), "application/octet-stream")

    def thumbnail(self, project_id: str, video_id: str) -> tuple[Path, bool]:
        """Return a cached thumbnail, decoding at most two source frames.

        This lazy operation is deliberately bounded so video-card requests can
        load independently without enqueueing heavyweight processing or
        repeatedly decoding a video. A cached placeholder is returned when the
        managed raw copy cannot yield a frame.
        """

        video = self._project_video(project_id, video_id)
        cached = self.storage.existing_thumbnail(project_id, video_id)
        if cached is not None:
            return cached

        target = self.storage.thumbnail_path(project_id, video_id)
        try:
            source = self.storage.raw_path(project_id, video["relative_path"])
            if self._generate_thumbnail(source, target, int(video["original_frame_count"])):
                return target, False
        except (OSError, VideoResourceNotFoundError, cv2.error):
            pass

        fallback = self.storage.thumbnail_path(project_id, video_id, fallback=True)
        self._write_thumbnail_placeholder(fallback)
        return fallback, True

    def delete_video(self, project_id: str, video_id: str) -> dict[str, Any]:
        """Delete one managed video without touching external or project-wide files."""

        video = self._project_video(project_id, video_id)
        try:
            staging = self.storage.stage_video_deletion(project_id, video_id)
        except OSError as exc:
            raise VideoValidationError(
                "Video files are currently in use; stop playback or processing and try again"
            ) from exc
        try:
            deleted = self.repository.delete_video(project_id, video_id)
        except Exception:
            self.storage.restore_staged_video(project_id, staging)
            raise
        self.storage.finalize_staged_video(staging)
        return {
            "video_id": deleted["video_id"],
            "filename": deleted["filename"],
            "deleted": True,
            "owned_copy_removed": True,
        }

    def rename_videos(self, project_id: str, prefix: str) -> list[dict[str, Any]]:
        """Rename every displayed video name using a stable numeric sequence."""

        clean_prefix = prefix.strip()
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", clean_prefix):
            raise VideoValidationError(
                "Prefix must start with a letter or number and use only letters, numbers, hyphens, or underscores"
            )
        videos = sorted(
            self.repository.list_videos(project_id),
            key=lambda video: str(video["filename"]).casefold(),
        )
        filename_map = {
            str(video["video_id"]): f"{clean_prefix}_{index:05d}{Path(str(video['filename'])).suffix.lower()}"
            for index, video in enumerate(videos, start=1)
        }
        self.repository.rename_videos(project_id, filename_map)
        return self.repository.list_videos(project_id)

    def trim_video(
        self,
        project_id: str,
        video_id: str,
        start_frame: int,
        end_frame: int,
        save_mode: str,
        filename: str | None = None,
        suggestion_mode: str = "threshold",
    ) -> dict[str, Any]:
        """Re-encode one selected frame range as a replacement or clean copy.

        Trim coordinates use the canonical timeline shown in the UI. The raw
        frame mapping converts those coordinates back to the source video so
        the saved clip precisely represents the selected visual range.
        """

        video = self._project_video(project_id, video_id)
        total_frames = int(video["canonical_frame_count"])
        if not 0 <= start_frame < end_frame < total_frames:
            raise VideoValidationError("Choose a trim range with at least two frames")
        if end_frame - start_frame + 1 < WINDOW_LENGTH_FRAMES:
            raise VideoValidationError(
                f"Trimmed video must contain at least {WINDOW_LENGTH_FRAMES} frames "
                "to create one analysis window"
            )
        if save_mode not in {"replace", "copy"}:
            raise VideoValidationError("Trim destination must be replace or copy")
        if self.repository.active_job_for_video(video_id) is not None:
            raise VideoValidationError("Wait for this video's processing to finish before trimming it")

        source = self.storage.raw_path(project_id, str(video["relative_path"]))
        annotation_snapshot = self.repository.trimmed_annotation_snapshot(
            video_id, start_frame, end_frame
        )
        mapping = self.repository.frame_mapping(video_id)
        source_start, source_end = self._source_trim_bounds(video, mapping, start_frame, end_frame)
        raw_directory = self.storage.ensure_project(project_id) / "raw"
        output_id = video_id if save_mode == "replace" else uuid4().hex
        final_path = raw_directory / f"{output_id}.mp4"
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{output_id}.trim-", suffix=".mp4", dir=raw_directory
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            self._write_trimmed_media(source, temporary, source_start, source_end)
            metadata = self._probe(temporary)
            output_mapping = canonical_frame_mapping(
                metadata["original_fps"], metadata["original_frame_count"]
            )
            if save_mode == "copy":
                os.replace(temporary, final_path)
                values = self._trimmed_video_values(
                    video, final_path, metadata, filename, is_copy=True
                )
                copy = self.repository.create_video(project_id, values, video_id=output_id)
                self.repository.replace_frame_mapping(output_id, output_mapping)
                self.repository.restore_trimmed_annotations(
                    output_id, annotation_snapshot, start_frame, end_frame
                )
                processing_action, jobs = self._prepare_trimmed_video(
                    project_id, video, output_id, annotation_snapshot,
                    start_frame, end_frame, suggestion_mode,
                )
                return {
                    "video": self.repository.get_video(copy["video_id"]),
                    "save_mode": "copy", "processing_action": processing_action,
                    "jobs": jobs,
                }

            backup = raw_directory / f".{video_id}.pre-trim{source.suffix.lower()}"
            if backup.exists():
                backup.unlink()
            try:
                os.replace(source, backup)
                os.replace(temporary, final_path)
                values = self._trimmed_video_values(video, final_path, metadata, None)
                replaced = self.repository.reset_trimmed_video(
                    video_id, values, output_mapping
                )
                self.repository.restore_trimmed_annotations(
                    video_id, annotation_snapshot, start_frame, end_frame
                )
                can_copy_pose = bool(annotation_snapshot["segments"]) and self._can_copy_trimmed_pose(
                    project_id, video, start_frame, end_frame
                )
                if not can_copy_pose:
                    self.storage.remove_artifacts(
                        project_id, video_id,
                        ("canonical", "pose", "features", "thumbnails", "overlays"),
                    )
                processing_action, jobs = self._prepare_trimmed_video(
                    project_id, video, video_id, annotation_snapshot,
                    start_frame, end_frame, suggestion_mode,
                )
                if can_copy_pose:
                    self.storage.remove_artifacts(
                        project_id, video_id,
                        ("canonical", "features", "thumbnails", "overlays"),
                    )
                replaced = self.repository.get_video(video_id)
            except Exception:
                if final_path.exists() and backup.exists():
                    final_path.unlink()
                if backup.exists():
                    os.replace(backup, source)
                raise
            backup.unlink(missing_ok=True)
            return {
                "video": replaced, "save_mode": "replace",
                "processing_action": processing_action, "jobs": jobs,
            }
        except OSError as exc:
            raise VideoValidationError(
                "Trim could not be saved because the video file is currently in use"
            ) from exc
        except cv2.error as exc:
            raise VideoValidationError("Video could not be trimmed") from exc
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _source_trim_bounds(
        video: dict[str, Any],
        mapping: list[dict[str, Any]],
        start_frame: int,
        end_frame: int,
    ) -> tuple[int, int]:
        """Map inclusive canonical bounds to inclusive raw-video frame bounds."""

        if len(mapping) > end_frame:
            return int(mapping[start_frame]["original_frame"]), int(mapping[end_frame]["original_frame"])
        ratio = float(video["original_fps"]) / float(video["canonical_fps"])
        return round(start_frame * ratio), round(end_frame * ratio)

    def _prepare_trimmed_video(
        self,
        project_id: str,
        source: dict[str, Any],
        trimmed_video_id: str,
        annotation_snapshot: dict[str, list[dict[str, Any]]],
        start_frame: int,
        end_frame: int,
        suggestion_mode: str,
    ) -> tuple[str, list[dict[str, Any]]]:
        """Reuse pose data for saved labels or queue a new suggestion pipeline."""

        if annotation_snapshot["segments"] and self._copy_trimmed_pose(
            project_id, source, trimmed_video_id, start_frame, end_frame
        ):
            return "keypoints_copied", []
        jobs = self.queue_pipeline(
            project_id, trimmed_video_id, suggestion_mode, priority=500
        )
        return "suggestions_queued", jobs

    def _copy_trimmed_pose(
        self,
        project_id: str,
        source: dict[str, Any],
        trimmed_video_id: str,
        start_frame: int,
        end_frame: int,
    ) -> bool:
        """Slice a compatible source pose cache and preserve its worker IDs."""

        if not self._can_copy_trimmed_pose(project_id, source, start_frame, end_frame):
            return False
        version = str(source["pose_cache_version"])
        tracking_version = str(source["tracking_cache_version"])
        source_path = self.storage.artifact_path(
            project_id, "pose", str(source["video_id"]), version
        )
        pose = self.storage.read_json(source_path)
        frames = [
            {**frame, "frame_index": int(frame["frame_index"]) - start_frame}
            for frame in pose.get("frames", [])
            if start_frame <= int(frame["frame_index"]) <= end_frame
        ]
        if not frames:
            return False
        pose["video_id"] = trimmed_video_id
        pose["frames"] = frames
        self.storage.write_json(
            self.storage.artifact_path(project_id, "pose", trimmed_video_id, str(version)),
            pose,
        )
        self.repository.update_video(
            trimmed_video_id,
            pose_cache_version=version,
            tracking_cache_version=tracking_version,
            processing_status="annotation_ready",
            quality_status=source.get("quality_status", "unknown"),
        )
        return True

    def _can_copy_trimmed_pose(
        self,
        project_id: str,
        source: dict[str, Any],
        start_frame: int,
        end_frame: int,
    ) -> bool:
        """Check whether the saved range has a compatible source pose cache."""

        version = source.get("pose_cache_version")
        if not version or not source.get("tracking_cache_version"):
            return False
        path = self.storage.artifact_path(
            project_id, "pose", str(source["video_id"]), str(version)
        )
        if not path.is_file():
            return False
        pose = self.storage.read_json(path)
        return any(
            start_frame <= int(frame["frame_index"]) <= end_frame
            for frame in pose.get("frames", [])
        )

    @staticmethod
    def _write_trimmed_media(source: Path, target: Path, start: int, end: int) -> None:
        """Encode an inclusive raw-frame range as browser-compatible H.264 MP4."""

        capture = cv2.VideoCapture(str(source))
        try:
            if not capture.isOpened():
                raise VideoValidationError("Video could not be opened for trimming")
            fps = float(capture.get(cv2.CAP_PROP_FPS))
        finally:
            capture.release()
        if fps <= 0:
            raise VideoValidationError("Video frame rate is unavailable for trimming")

        command = [
            get_ffmpeg_exe(), "-y", "-i", str(source),
            "-vf", f"trim=start_frame={start}:end_frame={end + 1},setpts=PTS-STARTPTS",
            "-map", "0:v:0", "-an",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", f"{fps:g}",
            "-movflags", "+faststart", str(target),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, check=False)
        if completed.returncode != 0 or not target.is_file() or target.stat().st_size == 0:
            raise VideoValidationError("Video could not be encoded as a browser-compatible MP4")

    def _trimmed_video_values(
        self,
        original: dict[str, Any],
        output: Path,
        metadata: dict[str, Any],
        requested_filename: str | None,
        is_copy: bool = False,
    ) -> dict[str, Any]:
        """Build a clean imported-video row for a freshly encoded trim."""

        digest = hashlib.sha256()
        with output.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        filename = self._trimmed_filename(
            str(original["filename"]), requested_filename, is_copy
        )
        return {
            "filename": filename,
            "relative_path": str(
                output.relative_to(self.storage.project_dir(str(original["project_id"])))
            ).replace("\\", "/"),
            "file_hash": digest.hexdigest(),
            "canonical_fps": 24,
            "canonical_frame_count": len(canonical_frame_mapping(metadata["original_fps"], metadata["original_frame_count"])),
            "file_size": output.stat().st_size,
            "folder_group": original.get("folder_group"),
            **metadata,
        }

    @staticmethod
    def _trimmed_filename(
        original_filename: str, requested_filename: str | None, is_copy: bool
    ) -> str:
        """Return a safe displayed filename for an MP4 trim output."""

        if requested_filename is None or not requested_filename.strip():
            if not is_copy:
                return original_filename
            return f"{Path(original_filename).stem}_copy.mp4"
        clean = requested_filename.strip()
        if Path(clean).name != clean or any(character in clean for character in "<>:\\|?*"):
            raise VideoValidationError("Copy name must be a simple file name")
        return clean if Path(clean).suffix.lower() == ".mp4" else f"{Path(clean).stem}.mp4"

    def overlay_range(self, project_id: str, video_id: str, start: int, end: int) -> list[dict[str, Any]]:
        video = self._project_video(project_id, video_id)
        if not video.get("pose_cache_version"):
            return []
        artifact = self.storage.read_json(
            self.storage.artifact_path(project_id, "pose", video_id, video["pose_cache_version"])
        )
        return [frame for frame in artifact["frames"] if start <= int(frame["frame_index"]) <= end]

    def list_jobs(self, project_id: str) -> list[dict[str, Any]]:
        return self.repository.list_jobs(project_id)

    def save_workspace_state(self, project_id: str, state: dict[str, Any]) -> dict[str, Any]:
        self.repository.save_workspace_state(project_id, state)
        return self.repository.workspace_state(project_id) or {}

    def update_project(self, project_id: str, config: dict[str, Any]) -> dict[str, Any]:
        validate_project_config(config)
        old = self.repository.get_project(project_id)["config"]
        project = self.repository.update_project(project_id, config)
        if old.get("pose") != config.get("pose"):
            self._invalidate_all(project_id, ("pose", "canonical", "features"), "imported")
        elif old.get("tracking") != config.get("tracking"):
            self._invalidate_all(project_id, ("pose", "features"), "pose_ready")
        elif old.get("features") != config.get("features"):
            self._invalidate_all(project_id, ("features",), "annotation_ready")
        elif old.get("window") != config.get("window") or old.get("window_labeling") != config.get("window_labeling"):
            for video in self.repository.list_videos(project_id):
                self.repository.execute("UPDATE generated_windows SET stale=1 WHERE video_id=?", (video["video_id"],))
                self.repository.update_video(video["video_id"], window_cache_version=None)
        return project

    def import_video(self, project_id: str, filename: str, source: BinaryIO) -> dict[str, Any]:
        self.repository.get_project(project_id)
        video_id = uuid4().hex
        raw_path, digest, size = self.storage.save_raw(project_id, video_id, filename, source)
        try:
            metadata = self._probe(raw_path)
            mapping = canonical_frame_mapping(metadata["original_fps"], metadata["original_frame_count"])
            if len(mapping) < WINDOW_LENGTH_FRAMES:
                raise VideoValidationError(
                    f'"{Path(filename).name}" is too short for video labeling: '
                    f"it has {len(mapping)} frames on the 24 FPS annotation timeline. "
                    f"At least {WINDOW_LENGTH_FRAMES} frames are required for one analysis window."
                )
            values = {
                "filename": Path(filename).name,
                "relative_path": str(raw_path.relative_to(self.storage.project_dir(project_id))).replace("\\", "/"),
                "file_hash": digest,
                "canonical_fps": 24,
                "canonical_frame_count": len(mapping),
                "file_size": size,
                "folder_group": Path(filename).parent.name if Path(filename).parent.name not in {"", "."} else None,
                **metadata,
            }
            video = self.repository.create_video(project_id, values, video_id=video_id)
            self.repository.replace_frame_mapping(video_id, mapping)
            return video
        except sqlite3.IntegrityError as exc:
            self.storage.delete_raw(raw_path)
            raise DuplicateVideoError("This exact video is already imported in the project") from exc
        except Exception:
            self.storage.delete_raw(raw_path)
            raise

    @staticmethod
    def _probe(path: Path) -> dict[str, Any]:
        capture = cv2.VideoCapture(str(path))
        try:
            if not capture.isOpened():
                raise VideoValidationError("Video could not be opened")
            fps = float(capture.get(cv2.CAP_PROP_FPS))
            frames = int(capture.get(cv2.CAP_PROP_FRAME_COUNT))
            width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
            codec_int = int(capture.get(cv2.CAP_PROP_FOURCC))
            codec = "".join(chr((codec_int >> (8 * index)) & 0xFF) for index in range(4)).strip("\x00")
            if fps <= 0 or frames <= 0 or width <= 0 or height <= 0:
                raise VideoValidationError("Video metadata is incomplete or invalid")
            return {
                "original_fps": fps,
                "original_frame_count": frames,
                "duration_seconds": frames / fps,
                "width": width,
                "height": height,
                "codec": codec or None,
            }
        finally:
            capture.release()

    def processing_options(self, project_id: str) -> dict[str, Any]:
        """Return annotator-safe processing-mode availability."""

        self.repository.get_project(project_id)
        model = self.repository.active_external_model(project_id)
        available = bool(
            model
            and model.get("compatibility_status") == "compatible"
            and Path(str(model.get("artifact_path", ""))).is_file()
        )
        return {
            "threshold_available": True,
            "model_available": available,
            "model_message": (
                None
                if available
                else "Model suggestions are not configured for this project."
            ),
        }

    def queue_pipeline(
        self,
        project_id: str,
        video_id: str,
        mode: str = "threshold",
        priority: int = 100,
        overwrite_labels: bool = False,
    ) -> list[dict[str, Any]]:
        """Queue one mode-aware pipeline from the deepest valid cache."""

        video = self._project_video(project_id, video_id)
        target_mode = mode.strip().lower()
        if target_mode not in {"threshold", "model"}:
            raise VideoValidationError("Processing mode must be threshold or model")

        model_id: str | None = None
        if target_mode == "model":
            model = self.repository.active_external_model(project_id)
            if not model or model.get("compatibility_status") != "compatible":
                raise ModelCompatibilityError(
                    "Model suggestions are not configured for this project."
                )
            if not Path(str(model.get("artifact_path", ""))).is_file():
                raise ModelCompatibilityError(
                    "Model suggestions are temporarily unavailable."
                )
            model_id = str(model["external_model_id"])

        if overwrite_labels:
            self._clear_labels_for_suggestion_overwrite(video_id)

        stage = self._first_pipeline_stage(video, target_mode)
        job = self.repository.enqueue_pipeline_job(
            project_id,
            video_id,
            stage,
            target_mode,
            model_id,
            priority,
        )
        return [job]

    def _clear_labels_for_suggestion_overwrite(self, video_id: str) -> None:
        """Remove current labels after the annotator explicitly confirmed replacement."""

        video = self.repository.get_video(video_id)
        revision = int(video["annotation_revision"])
        segments = self.repository.list_segments(video_id)
        for segment in segments:
            revision = self.repository.delete_segment(video_id, segment["segment_id"], revision)
        if segments:
            self.repository.update_video(
                video_id,
                annotation_status="unlabeled",
                is_approved=0,
                approval_revision=None,
                approved_at=None,
            )

    def _first_pipeline_stage(
        self,
        video: dict[str, Any],
        target_mode: str,
    ) -> str:
        """Select prerequisites from durable artifacts instead of status text."""

        project_id = str(video["project_id"])
        video_id = str(video["video_id"])
        canonical_ready = self.storage.canonical_path(project_id, video_id).is_file()
        pose_version = video.get("pose_cache_version")
        pose_ready = bool(
            pose_version
            and video.get("tracking_cache_version") == TRACKING_CACHE_VERSION
            and self.storage.artifact_path(
                project_id,
                "pose",
                video_id,
                str(pose_version),
            ).is_file()
        )
        feature_version = video.get("feature_cache_version")
        feature_ready = bool(
            pose_ready
            and
            feature_version == FEATURE_SCHEMA_VERSION
            and video.get("window_cache_version") == WINDOW_CONFIG_VERSION
            and self.storage.artifact_path(
                project_id,
                "features",
                video_id,
                FEATURE_SCHEMA_VERSION,
            ).is_file()
        )
        if feature_ready:
            return target_mode
        if pose_ready:
            return "features"
        if canonical_ready:
            return "pose_track"
        return "canonicalize"

    def control_job(self, job_id: str, action: str) -> dict[str, Any]:
        job = self.repository.get_job(job_id)
        if action == "pause":
            if job["status"] == "queued":
                return self.repository.update_job(job_id, status="paused", control_requested=None)
            return self.repository.update_job(job_id, control_requested="pause")
        if action == "resume":
            if job["status"] != "paused":
                raise VideoValidationError("Only paused jobs can be resumed")
            return self.repository.update_job(job_id, status="queued", control_requested=None, error_message=None)
        if action == "cancel":
            if job["status"] in {"completed", "failed", "cancelled"}:
                return job
            if job["status"] in {"queued", "paused"}:
                return self.repository.update_job(
                    job_id,
                    status="cancelled",
                    control_requested=None,
                    finished_at=self.repository.one("SELECT CURRENT_TIMESTAMP AS value")["value"],
                )
            return self.repository.update_job(job_id, control_requested="cancel")
        if action == "retry":
            if job["status"] not in {"failed", "cancelled"}:
                raise VideoValidationError("Only failed or cancelled jobs can be retried")
            return self.repository.retry_job(job_id)
        if action == "prioritize":
            return self.repository.update_job(job_id, priority=max(1000, int(job["priority"]) + 100))
        raise VideoValidationError("Unknown job control action")

    def set_video_inclusion(self, video_id: str, include: bool, reason: str | None = None) -> dict[str, Any]:
        if not include and not reason:
            raise VideoValidationError("An exclusion reason is required")
        return self.repository.update_video(
            video_id,
            include_in_export=int(include),
            exclude_reason=None if include else reason,
            annotation_status=self.repository.get_video(video_id)["annotation_status"] if include else "excluded",
            quality_status="good" if include else "excluded",
        )

    def prioritize_opened_video(self, video_id: str) -> None:
        video = self.repository.get_video(video_id)
        self.repository.execute(
            "UPDATE processing_jobs SET priority=MAX(priority,1000),updated_at=CURRENT_TIMESTAMP WHERE video_id=? AND status='queued'",
            (video_id,),
        )
        self.repository.save_workspace_state(video["project_id"], {"video_id": video_id})

    def _invalidate_all(
        self,
        project_id: str,
        categories: tuple[str, ...],
        status: str,
    ) -> None:
        for video in self.repository.list_videos(project_id):
            self.storage.remove_artifacts(project_id, video["video_id"], categories)
            self.repository.update_video(
                video["video_id"], processing_status=status, pose_cache_version=None,
                tracking_cache_version=None, feature_cache_version=None,
                threshold_cache_version=None, window_cache_version=None,
            )

    def _project_video(self, project_id: str, video_id: str) -> dict[str, Any]:
        """Fetch a video while enforcing its project boundary."""

        video = self.repository.get_video(video_id)
        if video["project_id"] != project_id:
            raise VideoResourceNotFoundError("Video not found in project")
        return video

    def _generate_thumbnail(
        self,
        source: Path,
        target: Path,
        frame_count: int,
    ) -> bool:
        """Decode a representative frame and atomically cache a letterboxed JPEG."""

        capture = cv2.VideoCapture(str(source))
        try:
            if not capture.isOpened():
                return False
            capture.set(cv2.CAP_PROP_POS_FRAMES, max(0, frame_count // 3))
            decoded, frame = capture.read()
            if not decoded:
                capture.set(cv2.CAP_PROP_POS_FRAMES, 0)
                decoded, frame = capture.read()
            if not decoded or frame is None or frame.size == 0:
                return False
        finally:
            capture.release()

        height, width = frame.shape[:2]
        scale = min(THUMBNAIL_WIDTH / width, THUMBNAIL_HEIGHT / height)
        resized_width = max(1, round(width * scale))
        resized_height = max(1, round(height * scale))
        resized = cv2.resize(frame, (resized_width, resized_height), interpolation=cv2.INTER_AREA)
        canvas = np.full((THUMBNAIL_HEIGHT, THUMBNAIL_WIDTH, 3), 20, dtype=np.uint8)
        left = (THUMBNAIL_WIDTH - resized_width) // 2
        top = (THUMBNAIL_HEIGHT - resized_height) // 2
        canvas[top : top + resized_height, left : left + resized_width] = resized
        encoded, buffer = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 82])
        if not encoded:
            return False
        self.storage.write_bytes(target, buffer.tobytes())
        return True

    def _write_thumbnail_placeholder(self, target: Path) -> None:
        """Cache a compact neutral fallback preview for an unreadable video."""

        canvas = np.full((THUMBNAIL_HEIGHT, THUMBNAIL_WIDTH, 3), 28, dtype=np.uint8)
        cv2.rectangle(canvas, (1, 1), (THUMBNAIL_WIDTH - 2, THUMBNAIL_HEIGHT - 2), (74, 90, 86), 2)
        cv2.putText(
            canvas,
            "Preview unavailable",
            (70, 96),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (186, 202, 197),
            1,
            cv2.LINE_AA,
        )
        encoded, buffer = cv2.imencode(".jpg", canvas, [cv2.IMWRITE_JPEG_QUALITY, 78])
        if not encoded:
            raise VideoValidationError("Unable to create thumbnail placeholder")
        self.storage.write_bytes(target, buffer.tobytes())
