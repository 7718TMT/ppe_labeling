"""API coverage for the dedicated read-only behavior inference workspace."""

from __future__ import annotations

from pathlib import Path

import cv2
import joblib
import numpy as np
from fastapi.testclient import TestClient

from backend.app.api.dependencies.video import (
    get_behavior_inference_service,
    get_video_service,
)
from backend.app.main import create_app
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.behavior_inference_service import BehaviorInferenceService
from backend.app.services.video_service import VideoService


class BehaviorTestModel:
    """Minimal serializable probability model used to register the fixed model."""

    classes_ = np.asarray([0, 1, 2])

    def predict_proba(self, matrix: np.ndarray) -> np.ndarray:
        return np.tile(
            np.asarray([[.8, .1, .1]], dtype=np.float32),
            (len(matrix), 1),
        )


def _video_bytes(tmp_path: Path) -> bytes:
    """Create the minimum supported 60-frame fixture."""

    path = tmp_path / "inference.mp4"
    writer = cv2.VideoWriter(
        str(path), cv2.VideoWriter_fourcc(*"mp4v"), 24, (32, 24)
    )
    for index in range(60):
        writer.write(np.full((24, 32, 3), index, dtype=np.uint8))
    writer.release()
    return path.read_bytes()


def test_inference_workspace_is_hidden_and_upload_queues_model_pipeline(
    tmp_path: Path,
) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    model_path = tmp_path / "behavior.joblib"
    joblib.dump(BehaviorTestModel(), model_path)
    service = BehaviorInferenceService(repository, storage, model_path)
    app = create_app()
    app.dependency_overrides[get_behavior_inference_service] = lambda: service
    app.dependency_overrides[get_video_service] = lambda: VideoService(
        repository, storage
    )

    with TestClient(app) as client:
        workspace = client.get("/api/v1/behavior-inference")
        assert workspace.status_code == 200
        assert workspace.json()["model"]["name"] == "Behavior XGBoost"
        assert VideoService(repository, storage).list_projects() == []

        response = client.post(
            "/api/v1/behavior-inference/videos",
            files=[
                (
                    "files",
                    ("sample.mp4", _video_bytes(tmp_path), "video/mp4"),
                )
            ],
        )
        video = response.json()[0]
        thumbnail = client.get(
            "/api/v1/video-projects/"
            f"{video['project_id']}/videos/{video['video_id']}/thumbnail"
        )
        assert thumbnail.status_code == 200
        assert thumbnail.headers["content-type"] == "image/jpeg"
        for suffix in ("results.json", "events.csv", "annotated.mp4"):
            assert client.get(
                f"/api/v1/behavior-inference/videos/{video['video_id']}/{suffix}"
            ).status_code == 404

    assert response.status_code == 200
    jobs = repository.list_jobs(video["project_id"])
    assert len(jobs) == 1
    assert jobs[0]["stage"] == "canonicalize"
    assert jobs[0]["target_mode"] == "model"
    assert jobs[0]["external_model_id"] is not None
