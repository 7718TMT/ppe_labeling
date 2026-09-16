"""Read-only behavior inference workflow built on the video processing pipeline."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from backend.app.domain.errors import ModelUnavailableError, VideoValidationError
from backend.app.domain.video import (
    CANONICAL_FPS,
    FEATURE_SCHEMA_VERSION,
    WINDOW_LENGTH_FRAMES,
)
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_features import feature_columns
from backend.app.services.video_service import VideoService


INFERENCE_PROJECT_NAME = "Behavior inference"
LABELS = {"others": 0, "running": 1, "falling": 2}


class BehaviorInferenceService:
    """Own fixed-model inference sessions without exposing annotation controls."""

    def __init__(
        self,
        repository: VideoRepository,
        storage: VideoStorageRepository,
        model_path: Path,
        manifest_path: Path | None = None,
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.model_path = model_path
        self.manifest_path = manifest_path
        self.videos = VideoService(repository, storage)

    def workspace(self) -> dict[str, Any]:
        """Return the hidden inference project and its compact processing state."""

        project = self._project()
        model = self._model(project["project_id"])
        return {
            "project": project,
            "videos": self.repository.list_videos(project["project_id"]),
            "jobs": self.repository.list_jobs(project["project_id"]),
            "model": {"name": model["name"], "version": model["version"]},
        }

    def import_videos(self, uploads: list[tuple[str, BinaryIO]]) -> list[dict[str, Any]]:
        """Import videos and queue the full pose-to-model pipeline."""

        project = self._project()
        self._model(project["project_id"])
        imported = [
            self.videos.import_video(project["project_id"], name, source)
            for name, source in uploads
        ]
        for video in imported:
            self.videos.queue_pipeline(project["project_id"], video["video_id"], "model", 1000)
        return imported

    def results(self, video_id: str) -> dict[str, Any]:
        """Return tracks, raw window probabilities, and merged smoothed events."""

        project = self._project()
        video = self._video(project["project_id"], video_id)
        model = self._model(project["project_id"])
        windows = self.repository.all(
            """
            SELECT p.*,w.track_id,w.start_frame,w.end_frame,w.quality_status,w.quality_score
            FROM model_window_predictions p
            JOIN generated_windows w ON w.window_id=p.window_id
            WHERE p.external_model_id=? AND w.video_id=?
            ORDER BY w.track_id,w.start_frame
            """,
            (model["external_model_id"], video_id),
        )
        events = self.repository.list_suggestions("model_suggestions", video_id)
        tracks = self.repository.list_tracks(video_id)
        summaries = []
        for track in tracks:
            track_events = [
                row
                for row in events
                if int(row["track_id"]) == int(track["track_id"])
            ]
            summaries.append({
                **track,
                "falling_events": sum(
                    row["suggested_label"] == "falling" for row in track_events
                ),
                "running_events": sum(
                    row["suggested_label"] == "running" for row in track_events
                ),
            })
        return {
            "video": video,
            "tracks": tracks,
            "track_summaries": summaries,
            "windows": windows,
            "events": events,
        }

    def _project(self) -> dict[str, Any]:
        project = next(
            (
                item for item in self.repository.list_projects()
                if item["name"] == INFERENCE_PROJECT_NAME
            ),
            None,
        )
        return project or self.videos.create_project(INFERENCE_PROJECT_NAME)

    def _model(self, project_id: str) -> dict[str, Any]:
        if not self.model_path.is_file():
            raise ModelUnavailableError(f"Behavior model is missing at {self.model_path}")
        digest = hashlib.sha256(self.model_path.read_bytes()).hexdigest()
        manifest = self._manifest()
        version = manifest.get("version", digest[:12])
        existing = next(
            (
                item for item in self.repository.list_external_models(project_id)
                if item["name"] == manifest["name"]
                and item["version"] == version
                and item["artifact_hash"] == digest
            ),
            None,
        )
        if existing:
            return self.repository.activate_external_model(
                project_id, existing["external_model_id"]
            )
        model_id = uuid4().hex
        values = {
            "name": manifest["name"],
            "version": version,
            "artifact_path": str(self.model_path.resolve()),
            "artifact_hash": digest,
            "adapter_type": "joblib",
            "class_map_json": json.dumps(manifest["class_map"]),
            "feature_schema_version": manifest["feature_schema_version"],
            "feature_columns_json": json.dumps(manifest["feature_columns"]),
            "window_config_json": json.dumps({
                "length": manifest["window_length"],
                "stride": manifest["stride"],
                "canonical_fps": manifest["canonical_fps"],
            }),
            "compatibility_status": "compatible",
            "compatibility_errors_json": "[]",
            "metadata_json": json.dumps({
                "preprocessing": manifest["preprocessing"],
                "inference": manifest["inference"],
            }),
        }
        self.repository.create_external_model(project_id, model_id, values)
        return self.repository.activate_external_model(project_id, model_id)

    def _manifest(self) -> dict[str, Any]:
        """Load the artifact contract; retain the legacy XGBoost contract by default."""

        if self.manifest_path is None:
            columns = [
                name for name in feature_columns()
                if name not in {"track_gap_count", "valid_frame_ratio"}
            ]
            return {
                "name": "Behavior model",
                "class_map": LABELS,
                "feature_schema_version": FEATURE_SCHEMA_VERSION,
                "feature_columns": columns,
                "window_length": WINDOW_LENGTH_FRAMES,
                "stride": 12,
                "canonical_fps": CANONICAL_FPS,
                "preprocessing": "behavior_preprocess_v1",
                "inference": {"minimum_probability": 0.5, "maximum_merge_gap": 12},
            }
        if not self.manifest_path.is_file():
            raise ModelUnavailableError(
                f"Behavior model manifest is missing at {self.manifest_path}"
            )
        try:
            manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelUnavailableError("Behavior model manifest is not valid JSON") from exc
        required = {
            "name", "class_map", "feature_schema_version", "feature_columns",
            "window_length", "stride", "canonical_fps",
        }
        missing = sorted(required - set(manifest))
        if missing:
            raise ModelUnavailableError(
                "Behavior model manifest is missing: " + ", ".join(missing)
            )
        manifest.setdefault("preprocessing", "raw")
        manifest.setdefault("inference", {"minimum_probability": 0.5, "maximum_merge_gap": 12})
        return manifest

    def _video(self, project_id: str, video_id: str) -> dict[str, Any]:
        video = self.repository.get_video(video_id)
        if video["project_id"] != project_id:
            raise VideoValidationError(
                "Video is outside the behavior inference workspace"
            )
        return video
