"""Regression coverage for managed video media, previews, and deletion."""

from __future__ import annotations

import io
import json
from pathlib import Path
from uuid import uuid4

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_video_service
from backend.app.domain.errors import VideoResourceNotFoundError
from backend.app.main import create_app
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import (
    VIDEO_SCOPED_DIRECTORIES,
    VideoStorageRepository,
)
from backend.app.services.video_annotation_service import VideoAnnotationService
from backend.app.services.video_service import VideoService


def _video_bytes(
    tmp_path: Path,
    name: str,
    base_value: int,
    frames: int = 60,
) -> bytes:
    path = tmp_path / name
    writer = cv2.VideoWriter(
        str(path),
        cv2.VideoWriter_fourcc(*"mp4v"),
        24.0,
        (64, 36),
    )
    assert writer.isOpened()
    for index in range(frames):
        value = min(255, base_value + index * 4)
        writer.write(np.full((36, 64, 3), value, dtype=np.uint8))
    writer.release()
    return path.read_bytes()


@pytest.fixture
def video_backend(tmp_path: Path):
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    service = VideoService(repository, storage)
    app = create_app()
    app.dependency_overrides[get_video_service] = lambda: service
    with TestClient(app) as client:
        yield client, repository, storage, service


def _track(end_frame: int) -> dict[str, object]:
    return {
        "track_id": 1,
        "start_frame": 0,
        "end_frame": end_frame,
        "valid_frame_count": end_frame + 1,
        "gap_count": 0,
        "avg_person_confidence": 0.9,
        "avg_keypoint_confidence": 0.9,
        "valid_frame_ratio": 1.0,
        "missing_ankle_ratio": 0.0,
        "quality_status": "good",
        "include_in_export": 1,
        "exclude_reason": None,
    }


def test_media_endpoint_serves_owned_raw_with_range_support(
    video_backend,
    tmp_path: Path,
) -> None:
    client, _repository, storage, service = video_backend
    project = service.create_project("Browser media")
    raw = _video_bytes(tmp_path, "browser.mp4", 20)
    video = service.import_video(
        project["project_id"],
        "browser.mp4",
        io.BytesIO(raw),
    )

    canonical = storage.canonical_path(project["project_id"], video["video_id"])
    storage.write_bytes(canonical, b"worker-only-fmp4-cache")
    endpoint = (
        f"/api/v1/video-projects/{project['project_id']}"
        f"/videos/{video['video_id']}/media"
    )

    response = client.get(endpoint)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("video/mp4")
    assert response.content == raw

    ranged = client.get(endpoint, headers={"Range": "bytes=0-15"})
    assert ranged.status_code == 206
    assert ranged.headers["content-range"] == f"bytes 0-15/{len(raw)}"
    assert ranged.content == raw[:16]


def test_thumbnail_endpoint_caches_preview_and_serves_fallback(
    video_backend,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, repository, storage, service = video_backend
    project = service.create_project("Previews")
    video = service.import_video(
        project["project_id"],
        "preview.mp4",
        io.BytesIO(_video_bytes(tmp_path, "preview.mp4", 80)),
    )
    endpoint = (
        f"/api/v1/video-projects/{project['project_id']}"
        f"/videos/{video['video_id']}/thumbnail"
    )

    generated = client.get(endpoint)
    assert generated.status_code == 200
    assert generated.headers["content-type"].startswith("image/jpeg")
    assert generated.headers["x-thumbnail-fallback"] == "false"
    decoded = cv2.imdecode(
        np.frombuffer(generated.content, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )
    assert decoded.shape[:2] == (180, 320)
    assert storage.thumbnail_path(
        project["project_id"], video["video_id"]
    ).is_file()

    def fail_regeneration(*_args, **_kwargs):
        pytest.fail("a cached thumbnail must not be regenerated")

    monkeypatch.setattr(service, "_generate_thumbnail", fail_regeneration)
    cached = client.get(endpoint)
    assert cached.status_code == 200
    assert cached.content == generated.content

    missing = repository.create_video(
        project["project_id"],
        {
            "filename": "missing.mp4",
            "relative_path": "raw/missing.mp4",
            "file_hash": "missing-preview",
            "original_fps": 24.0,
            "canonical_fps": 24.0,
            "original_frame_count": 24,
            "canonical_frame_count": 24,
            "duration_seconds": 1.0,
            "width": 64,
            "height": 36,
            "codec": "mp4v",
            "file_size": 0,
        },
    )
    fallback = client.get(
        f"/api/v1/video-projects/{project['project_id']}"
        f"/videos/{missing['video_id']}/thumbnail"
    )
    assert fallback.status_code == 200
    assert fallback.headers["x-thumbnail-fallback"] == "true"
    assert storage.thumbnail_path(
        project["project_id"],
        missing["video_id"],
        fallback=True,
    ).is_file()


def test_delete_video_cascades_structured_data_and_removes_only_owned_files(
    video_backend,
    tmp_path: Path,
) -> None:
    client, repository, storage, service = video_backend
    annotation = VideoAnnotationService(repository, storage)
    project = service.create_project("Safe delete")
    project_id = project["project_id"]
    external_source = tmp_path / "external-source.mp4"
    external_source.write_bytes(_video_bytes(tmp_path, "source.mp4", 25))
    first = service.import_video(
        project_id,
        "first.mp4",
        io.BytesIO(external_source.read_bytes()),
    )
    second = service.import_video(
        project_id,
        "second.mp4",
        io.BytesIO(_video_bytes(tmp_path, "second.mp4", 130)),
    )
    first_id = first["video_id"]
    second_id = second["video_id"]

    service.queue_pipeline(project_id, first_id, "threshold")
    service.queue_pipeline(project_id, second_id, "threshold")

    repository.replace_tracks(first_id, [_track(11)])
    repository.replace_tracks(second_id, [_track(11)])
    annotation.save_segment(first_id, 1, 0, 5, "others", 0)
    annotation.save_segment(second_id, 1, 0, 5, "running", 0)
    first_import_job = next(
        job
        for job in repository.list_jobs(project_id)
        if job["video_id"] == first_id
    )
    repository.update_job(
        first_import_job["job_id"],
        status="failed",
        error_message="synthetic failure",
    )
    repository.enqueue_job(project_id, "features", first_id)
    repository.replace_windows(
        first_id,
        [
            {
                "track_id": 1,
                "start_frame": 0,
                "end_frame": 11,
                "label": "others",
                "label_reason": "test",
                "quality_score": 1.0,
                "quality_status": "good",
                "include_in_export": 1,
                "exclude_reason": None,
                "window_config_version": "test-v1",
                "feature_status": "ready",
                "stale": 0,
            }
        ],
    )
    profile_id = repository.list_threshold_profiles(project_id)[0][
        "threshold_profile_id"
    ]
    repository.replace_threshold_suggestions(
        first_id,
        profile_id,
        [
            {
                "track_id": 1,
                "start_frame": 1,
                "end_frame": 4,
                "suggested_label": "running",
                "confidence": 0.8,
                "triggered_conditions_json": json.dumps(["test"]),
                "supporting_features_json": json.dumps({"speed": 1.0}),
                "quality_status": "good",
                "artifact_key": "delete-test",
            }
        ],
    )
    model_id = uuid4().hex
    repository.create_external_model(
        project_id,
        model_id,
        {
            "name": "shared-model",
            "version": "v1",
            "artifact_path": "models/shared-model.onnx",
            "artifact_hash": "shared-hash",
            "adapter_type": "onnx",
            "class_map_json": json.dumps(
                {"others": 0, "running": 1, "falling": 2}
            ),
            "feature_schema_version": "v1",
            "feature_columns_json": "[]",
            "window_config_json": json.dumps(
                {"length_frames": 60, "stride_frames": 12}
            ),
            "compatibility_status": "compatible",
            "compatibility_errors_json": "[]",
            "metadata_json": "{}",
            "is_active": 1,
        },
    )
    window_id = repository.list_windows(first_id)[0]["window_id"]
    repository.replace_model_predictions(
        model_id,
        first_id,
        [
            {
                "window_id": window_id,
                "others_probability": 0.05,
                "running_probability": 0.05,
                "falling_probability": 0.9,
                "predicted_label": "falling",
                "confidence": 0.9,
            }
        ],
        [
            {
                "track_id": 1,
                "start_frame": 1,
                "end_frame": 4,
                "suggested_label": "falling",
                "confidence": 0.9,
                "source_window_ids_json": json.dumps([window_id]),
                "probabilities_json": json.dumps({"falling": 0.9}),
                "merge_config_json": "{}",
            }
        ],
    )
    repository.save_workspace_state(
        project_id,
        {
            "video_id": first_id,
            "track_id": 1,
            "frame_index": 5,
            "suggestion_source": "AI",
        },
    )

    for category in VIDEO_SCOPED_DIRECTORIES:
        if category == "raw":
            continue
        first_path = storage.ensure_project(project_id) / category / f"{first_id}.cache"
        second_path = storage.ensure_project(project_id) / category / f"{second_id}.cache"
        storage.write_bytes(first_path, b"first")
        storage.write_bytes(second_path, b"second")
    shared_model = storage.ensure_project(project_id) / "models" / "shared-model.onnx"
    storage.write_bytes(shared_model, b"project-wide-model")

    response = client.delete(
        f"/api/v1/video-projects/{project_id}/videos/{first_id}"
    )
    assert response.status_code == 200
    assert response.json() == {
        "video_id": first_id,
        "filename": "first.mp4",
        "deleted": True,
        "owned_copy_removed": True,
    }

    with pytest.raises(VideoResourceNotFoundError):
        repository.get_video(first_id)
    assert repository.get_video(second_id)["filename"] == "second.mp4"
    assert repository.list_segments(second_id)[0]["label"] == "running"
    assert external_source.is_file()
    assert shared_model.read_bytes() == b"project-wide-model"

    for table in (
        "canonical_frame_mappings",
        "processing_jobs",
        "video_tracks",
        "video_segments",
        "annotation_history",
        "generated_windows",
        "threshold_suggestions",
        "model_suggestions",
    ):
        count = repository.one(
            f"SELECT COUNT(*) AS value FROM {table} WHERE video_id=?",
            (first_id,),
        )
        assert count == {"value": 0}
    assert repository.get_external_model(model_id)["name"] == "shared-model"
    assert repository.one(
        "SELECT COUNT(*) AS value FROM model_window_predictions "
        "WHERE external_model_id=?",
        (model_id,),
    ) == {"value": 0}
    assert any(
        job["video_id"] == second_id
        for job in repository.list_jobs(project_id)
    )

    workspace = repository.workspace_state(project_id)
    assert workspace is not None
    assert workspace["video_id"] is None
    assert workspace["track_id"] is None
    assert workspace["frame_index"] == 0
    assert workspace["suggestion_source"] == "AI"

    for category in VIDEO_SCOPED_DIRECTORIES:
        directory = storage.ensure_project(project_id) / category
        assert not any(
            path.name.startswith(first_id) for path in directory.iterdir()
        )
        assert any(
            path.name.startswith(second_id) for path in directory.iterdir()
        )
