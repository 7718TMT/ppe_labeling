"""Atomic reproducible exports for approved pose-video annotations."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import numpy as np

from backend.app.domain.video import HUMAN_LABELS
from backend.app.domain.errors import VideoResourceNotFoundError, VideoValidationError
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_feature_service import VideoFeatureService


class VideoExportService:
    """Validate then publish a complete export directory in one rename."""

    def __init__(self, repository: VideoRepository, storage: VideoStorageRepository, features: VideoFeatureService) -> None:
        self.repository = repository
        self.storage = storage
        self.features = features

    def validate(self, project_id: str) -> dict[str, list[str]]:
        errors: list[str] = []
        warnings: list[str] = []
        videos = self.repository.list_videos(project_id)
        included = [video for video in videos if video["include_in_export"]]
        approved = [video for video in included if video["is_approved"]]
        if not approved:
            errors.append("No included videos are approved")
        for video in included:
            if not video["is_approved"]:
                warnings.append(f"{video['filename']}: excluded because it is not approved")
                continue
            if not video.get("feature_cache_version"):
                errors.append(f"{video['filename']}: features are not ready")
            windows = self.repository.list_windows(video["video_id"])
            if not windows:
                errors.append(f"{video['filename']}: windows are not generated")
            unresolved = sum(not window["label"] for window in windows)
            low_quality = sum(window["quality_status"] == "low_quality" for window in windows)
            if unresolved:
                warnings.append(f"{video['filename']}: {unresolved} unresolved windows remain excluded")
            if low_quality:
                warnings.append(f"{video['filename']}: {low_quality} low-quality windows remain excluded")
        return {"errors": errors, "warnings": warnings}

    def list_exports(self, project_id: str) -> list[dict[str, Any]]:
        return self.repository.list_exports(project_id)

    def export_file(self, project_id: str, export_id: str, filename: str) -> Path:
        self._completed_export(project_id, export_id)
        return self.storage.export_file(project_id, export_id, filename)

    def export_archive(self, project_id: str, export_id: str) -> Path:
        """Return a ZIP archive after confirming the export belongs to this project."""

        self._completed_export(project_id, export_id)
        return self.storage.export_archive(project_id, export_id)

    def _completed_export(self, project_id: str, export_id: str) -> dict[str, Any]:
        export = self.repository.get_export(export_id)
        if export["project_id"] != project_id:
            raise VideoResourceNotFoundError("Export not found")
        if export["status"] != "completed":
            raise VideoValidationError("Export is not ready for download")
        return export

    def queue(self, project_id: str) -> dict[str, Any]:
        validation = self.validate(project_id)
        if validation["errors"]:
            return {"queued": False, "validation": validation}
        export = self.repository.create_export(project_id)
        job = self.repository.enqueue_job(project_id, f"export:{export['export_id']}", None, 80)
        self.repository.update_export(
            export["export_id"],
            job_id=job["job_id"],
            validation_json=json.dumps(validation),
        )
        return {"queued": True, "export": self.repository.get_export(export["export_id"]), "job": job, "validation": validation}

    def run_job(self, job: dict[str, Any], progress: Callable[[float], None]) -> None:
        export_id = str(job["stage"]).split(":", 1)[1]
        export = self.repository.get_export(export_id)
        project_id = export["project_id"]
        validation = self.validate(project_id)
        if validation["errors"]:
            self.repository.update_export(
                export_id,
                status="failed",
                validation_json=json.dumps(validation),
            )
            raise ValueError("Export validation failed: " + "; ".join(validation["errors"]))
        self.repository.update_export(
            export_id,
            status="running",
            validation_json=json.dumps(validation),
        )
        staging, final = self.storage.create_export_staging(project_id, export_id)
        try:
            self._generate(project_id, staging, progress)
            self.storage.publish_export(staging, final)
        except Exception:
            shutil.rmtree(staging, ignore_errors=True)
            self.repository.update_export(export_id, status="failed")
            raise
        manifest = json.loads((final / "manifest.json").read_text(encoding="utf-8"))
        self.repository.update_export(
            export_id,
            status="completed",
            artifact_path=str(final),
            manifest_json=json.dumps(manifest),
            validation_json=json.dumps(validation),
            finished_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        )

    def _generate(self, project_id: str, directory: Path, progress: Callable[[float], None]) -> None:
        project = self.repository.get_project(project_id)
        videos = [video for video in self.repository.list_videos(project_id) if video["include_in_export"] and video["is_approved"]]
        annotations: list[dict[str, Any]] = []
        keypoints: list[np.ndarray] = []
        keypoint_scores: list[np.ndarray] = []
        bboxes: list[np.ndarray] = []
        labels: list[int] = []
        video_hashes: dict[str, str] = {}
        for video_index, video in enumerate(videos):
            video_id = video["video_id"]
            video_hashes[video_id] = video["file_hash"]
            for segment in self.repository.list_segments(video_id):
                if segment["include_in_export"]:
                    annotations.append({key: segment[key] for key in ("video_id", "track_id", "start_frame", "end_frame", "label", "annotation_version")})
            windows = self.repository.list_windows(video_id)
            pose = self.storage.read_json(self.storage.artifact_path(project_id, "pose", video_id, video["pose_cache_version"]))
            track_frames: dict[int, dict[int, dict[str, Any]]] = {}
            for frame in pose["frames"]:
                for detection in frame["tracks"]:
                    track_frames.setdefault(int(detection["track_id"]), {})[int(frame["frame_index"])] = detection
            for window in windows:
                if window["include_in_export"] and window["label"]:
                    frames = [track_frames.get(int(window["track_id"]), {}).get(index) for index in range(int(window["start_frame"]), int(window["end_frame"]) + 1)]
                    keypoints.append(np.asarray([frame["keypoints"] if frame else [[0.0, 0.0]] * 17 for frame in frames], dtype=np.float32))
                    keypoint_scores.append(np.asarray([frame["keypoint_scores"] if frame else [0.0] * 17 for frame in frames], dtype=np.float32))
                    bboxes.append(np.asarray([frame["bbox"] if frame else [0.0] * 4 for frame in frames], dtype=np.float32))
                    labels.append(HUMAN_LABELS.index(window["label"]))
            progress((video_index + 1) / max(1, len(videos)) * 0.75)
        self._write_jsonl(directory / "annotations.jsonl", annotations)
        np.savez_compressed(
            directory / "keypoint_windows.npz",
            keypoints=np.stack(keypoints) if keypoints else np.empty((0, 60, 17, 2), dtype=np.float32),
            keypoint_scores=np.stack(keypoint_scores) if keypoint_scores else np.empty((0, 60, 17), dtype=np.float32),
            bboxes=np.stack(bboxes) if bboxes else np.empty((0, 60, 4), dtype=np.float32),
            labels=np.asarray(labels, dtype=np.int64),
        )
        progress(0.90)
        manifest = {
            "class_map": project["config"]["class_map"], "video_hashes": video_hashes,
            "pose": project["config"]["pose"], "tracking": project["config"]["tracking"],
            "canonical_fps": 24, "window": project["config"]["window"],
            "window_labeling": project["config"]["window_labeling"],
            "feature_schema_version": project["config"]["features"]["feature_schema_version"],
            "threshold_profile_id": project.get("active_threshold_profile_id"),
            "annotation_schema_version": project["config"]["annotation"]["annotation_schema_version"],
            "application_version": project["application_version"],
            "export_timestamp": datetime.now(timezone.utc).isoformat(),
            "files": {},
        }
        for path in sorted(directory.iterdir()):
            if path.name != "manifest.json":
                manifest["files"][path.name] = {"sha256": hashlib.sha256(path.read_bytes()).hexdigest(), "bytes": path.stat().st_size}
        (directory / "manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True), encoding="utf-8")
        progress(0.99)

    @staticmethod
    def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
        with path.open("w", encoding="utf-8", newline="\n") as output:
            for row in rows:
                output.write(json.dumps(row, separators=(",", ":"), sort_keys=True) + "\n")
