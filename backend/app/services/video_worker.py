"""Persistent local worker for heavyweight pose-video processing stages."""

from __future__ import annotations

import hashlib
import os
import socket
import time
from pathlib import Path
from typing import Any, Callable

import cv2

from backend.app.domain.errors import ModelUnavailableError, VideoValidationError
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_feature_service import VideoFeatureService


class JobInterrupted(Exception):
    """A worker observed a persistent pause or cancellation request."""

    def __init__(self, action: str) -> None:
        super().__init__(action)
        self.action = action


class VideoWorker:
    """Claim one SQLite job at a time and publish only complete cache files."""

    def __init__(
        self,
        repository: VideoRepository,
        storage: VideoStorageRepository,
        pose_model_path: Path,
        feature_service: VideoFeatureService,
        worker_id: str | None = None,
        extra_handlers: dict[str, Callable[[dict[str, Any], Callable[[float], None]], None]] | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.pose_model_path = pose_model_path
        self.feature_service = feature_service
        self.worker_id = worker_id or f"{socket.gethostname()}:{os.getpid()}"
        self.extra_handlers = extra_handlers or {}

    def recover(self) -> int:
        """Return orphaned running jobs to the queue after process restart."""

        return self.repository.recover_stale_jobs()

    def run_once(self) -> dict[str, Any] | None:
        job = self.repository.claim_job(self.worker_id)
        if job is None:
            return None
        try:
            progress = lambda value: self._progress(job["job_id"], value)
            stage = str(job["stage"])
            if stage == "canonicalize":
                self._canonicalize(job, progress)
            elif stage == "pose_track":
                self._pose_track(job, progress)
            elif stage == "features":
                self._features(job, progress)
            elif stage == "threshold":
                self._threshold(job, progress)
            elif stage in self.extra_handlers:
                self.extra_handlers[stage](job, progress)
            else:
                prefix = next((key for key in self.extra_handlers if key.endswith(":*") and stage.startswith(key[:-1])), None)
                if prefix:
                    self.extra_handlers[prefix](job, progress)
                else:
                    raise VideoValidationError(f"Unsupported worker stage: {stage}")
            self.repository.complete_job_and_enqueue_next(
                job["job_id"],
                self._next_stage(job),
            )
        except JobInterrupted as exc:
            status = "paused" if exc.action == "pause" else "cancelled"
            self.repository.update_job(job["job_id"], status=status, control_requested=None, finished_at=self._now() if status == "cancelled" else None)
        except Exception as exc:
            self.repository.update_job(job["job_id"], status="failed", error_message=str(exc), finished_at=self._now())
            if job.get("video_id"):
                self.repository.update_video(job["video_id"], processing_status="failed", last_error=str(exc))
        return self.repository.get_job(job["job_id"])

    def run_forever(self, poll_seconds: float = 0.5) -> None:
        while True:
            if self.run_once() is None:
                time.sleep(poll_seconds)

    def _canonicalize(self, job: dict[str, Any], progress: Callable[[float], None]) -> None:
        video = self.repository.get_video(job["video_id"])
        source = self.storage.raw_path(video["project_id"], video["relative_path"])
        target = self.storage.canonical_path(video["project_id"], video["video_id"])
        temporary = target.with_suffix(".processing.mp4")
        capture = cv2.VideoCapture(str(source))
        writer = cv2.VideoWriter(
            str(temporary), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (int(video["width"]), int(video["height"])),
        )
        mapping = self.repository.frame_mapping(video["video_id"])
        try:
            if not capture.isOpened() or not writer.isOpened():
                raise VideoValidationError("Unable to initialize canonical video processing")
            last_source = -1
            current_frame = None
            for index, row in enumerate(mapping):
                source_index = int(row["original_frame"])
                if source_index != last_source:
                    capture.set(cv2.CAP_PROP_POS_FRAMES, source_index)
                    ok, current_frame = capture.read()
                    if not ok:
                        raise VideoValidationError(f"Failed decoding source frame {source_index}")
                    last_source = source_index
                writer.write(current_frame)
                if index % 24 == 0:
                    progress((index + 1) / max(1, len(mapping)))
        finally:
            capture.release()
            writer.release()
        os.replace(temporary, target)
        self.repository.update_video(video["video_id"], processing_status="probed", last_error=None)

    def _pose_track(self, job: dict[str, Any], progress: Callable[[float], None]) -> None:
        if not self.pose_model_path.is_file():
            raise ModelUnavailableError(
                f"YOLO-Pose weights are missing at {self.pose_model_path}. Place yolo26m-pose weights there as pose.pt."
            )
        video = self.repository.get_video(job["video_id"])
        canonical = self.storage.canonical_path(video["project_id"], video["video_id"])
        if not canonical.is_file():
            raise VideoValidationError("Canonical video is not ready")
        from ultralytics import YOLO

        model_hash = hashlib.sha256(self.pose_model_path.read_bytes()).hexdigest()[:16]
        version = f"pose-v1-{model_hash}"
        model = YOLO(str(self.pose_model_path))
        results = model.track(
            source=str(canonical), stream=True, persist=True, tracker="bytetrack.yaml",
            conf=0.25, verbose=False,
        )
        frames: list[dict[str, Any]] = []
        summaries: dict[int, dict[str, Any]] = {}
        total = int(video["canonical_frame_count"])
        for frame_index, result in enumerate(results):
            tracks: list[dict[str, Any]] = []
            boxes = result.boxes
            keypoints = result.keypoints
            if boxes is not None and boxes.id is not None and keypoints is not None:
                ids = boxes.id.int().cpu().tolist()
                xyxy = boxes.xyxy.cpu().tolist()
                confidences = boxes.conf.cpu().tolist()
                points = keypoints.xy.cpu().tolist()
                scores = keypoints.conf.cpu().tolist() if keypoints.conf is not None else [[0.0] * 17 for _ in ids]
                for track_id, bbox, confidence, pose, pose_scores in zip(ids, xyxy, confidences, points, scores, strict=True):
                    detection = {
                        "track_id": int(track_id), "bbox": [float(value) for value in bbox],
                        "keypoints": [[float(value) for value in point] for point in pose],
                        "keypoint_scores": [float(value) for value in pose_scores],
                        "person_confidence": float(confidence),
                    }
                    tracks.append(detection)
                    summary = summaries.setdefault(int(track_id), {"frames": [], "person": [], "keypoint": [], "ankles_missing": 0})
                    summary["frames"].append(frame_index)
                    summary["person"].append(float(confidence))
                    summary["keypoint"].extend(float(value) for value in pose_scores)
                    summary["ankles_missing"] += int(any(float(pose_scores[index]) < 0.1 for index in (15, 16)))
            frames.append({"frame_index": frame_index, "tracks": tracks})
            if frame_index % 12 == 0:
                progress((frame_index + 1) / max(1, total))
        track_rows: list[dict[str, Any]] = []
        for track_id, summary in summaries.items():
            observed = sorted(summary["frames"])
            lifespan = observed[-1] - observed[0] + 1
            gaps = sum((right - left) > 1 for left, right in zip(observed, observed[1:], strict=False))
            valid_ratio = len(observed) / lifespan
            average_keypoint = sum(summary["keypoint"]) / max(1, len(summary["keypoint"]))
            track_rows.append({
                "track_id": track_id, "start_frame": observed[0], "end_frame": observed[-1],
                "valid_frame_count": len(observed), "gap_count": gaps,
                "avg_person_confidence": sum(summary["person"]) / len(summary["person"]),
                "avg_keypoint_confidence": average_keypoint, "valid_frame_ratio": valid_ratio,
                "missing_ankle_ratio": summary["ankles_missing"] / len(observed),
                "quality_status": "good" if average_keypoint >= 0.35 and valid_ratio >= 0.70 else "needs_review",
                "include_in_export": 1, "exclude_reason": None,
            })
        artifact = {"schema_version": "pose-v1", "model_version": model_hash, "video_id": video["video_id"], "frames": frames}
        self.storage.write_json(self.storage.artifact_path(video["project_id"], "pose", video["video_id"], version), artifact)
        has_annotations = bool(self.repository.list_segments(video["video_id"]))
        self.repository.replace_tracks(
            video["video_id"],
            track_rows,
            invalidate_derived=True,
            mark_annotations=has_annotations,
        )
        self.storage.remove_artifacts(
            video["project_id"],
            video["video_id"],
            ("features",),
        )
        self.repository.update_video(
            video["video_id"], pose_cache_version=version, tracking_cache_version="bytetrack-v1",
            processing_status="annotation_ready", quality_status="good" if track_rows else "low_quality", last_error=None,
        )

    def _features(self, job: dict[str, Any], progress: Callable[[float], None]) -> None:
        progress(0.05)
        self.feature_service.generate_windows(job["video_id"])
        progress(0.25)
        self.feature_service.extract_features(job["video_id"])
        progress(0.95)

    def _threshold(self, job: dict[str, Any], progress: Callable[[float], None]) -> None:
        progress(0.1)
        self.feature_service.generate_threshold_suggestions(job["video_id"])
        progress(0.95)

    @staticmethod
    def _next_stage(job: dict[str, Any]) -> str | None:
        """Return the next durable stage for the persisted target mode."""

        stage = str(job["stage"])
        if stage == "canonicalize":
            return "pose_track"
        if stage == "pose_track":
            return "features"
        if stage == "features":
            return str(job.get("target_mode") or "threshold")
        return None

    def _progress(self, job_id: str, value: float) -> None:
        job = self.repository.get_job(job_id)
        if job.get("control_requested") in {"pause", "cancel"}:
            raise JobInterrupted(str(job["control_requested"]))
        self.repository.update_job(job_id, progress=min(0.999, max(0.0, value)))

    def _now(self) -> str:
        return str(self.repository.one("SELECT CURRENT_TIMESTAMP AS value")["value"])
