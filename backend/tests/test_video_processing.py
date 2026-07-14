from concurrent.futures import ThreadPoolExecutor
import json
import sqlite3
from pathlib import Path
from threading import Barrier

import pytest

from backend.app.domain.errors import (
    ModelCompatibilityError,
    VideoProcessingConflictError,
)
from backend.app.domain.video import (
    FEATURE_SCHEMA_VERSION,
    TRACKING_CACHE_VERSION,
    WINDOW_CONFIG_VERSION,
)
from backend.app.repositories.video_db import SCHEMA_V1, VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_feature_service import VideoFeatureService
from backend.app.services.video_model_service import VideoModelService
from backend.app.services.video_service import VideoService
from backend.app.services.video_worker import (
    DEDICATED_REID_MODEL_PATH,
    DEDICATED_REID_TRACKER_CONFIG,
    DEDICATED_REID_TRACKER_VERSION,
    VideoWorker,
)


def test_dedicated_reid_tracker_profile_uses_separate_encoder() -> None:
    """The checked-in profile must select the dedicated appearance encoder."""

    from ultralytics.utils import YAML

    profile = YAML.load(DEDICATED_REID_TRACKER_CONFIG)

    assert DEDICATED_REID_TRACKER_VERSION == "botsort-dedicated-reid-v3"
    assert profile["tracker_type"] == "botsort"
    assert profile["with_reid"] is True
    assert profile["model"] == "weights/reid.pt"
    assert DEDICATED_REID_MODEL_PATH.name == "reid.pt"
    assert profile["track_buffer"] == 72
    assert profile["track_low_thresh"] == 0.05


def _create_video(
    repository: VideoRepository,
    project_id: str,
    file_hash: str = "processing-video",
) -> dict:
    return repository.create_video(
        project_id,
        {
            "filename": f"{file_hash}.mp4",
            "relative_path": f"raw/{file_hash}.mp4",
            "file_hash": file_hash,
            "original_fps": 24,
            "canonical_fps": 24,
            "original_frame_count": 60,
            "canonical_frame_count": 60,
            "duration_seconds": 2.5,
            "width": 100,
            "height": 200,
            "codec": "mp4v",
            "file_size": 1,
        },
    )


def _model_values(artifact: Path) -> dict:
    return {
        "name": "Configured model",
        "version": "1",
        "artifact_path": str(artifact),
        "artifact_hash": "model-hash",
        "adapter_type": "onnx",
        "class_map_json": json.dumps(
            {"others": 0, "running": 1, "falling": 2}
        ),
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "feature_columns_json": "[]",
        "window_config_json": json.dumps(
            {"length": 60, "stride": 12, "canonical_fps": 24}
        ),
        "compatibility_status": "compatible",
        "compatibility_errors_json": "[]",
        "metadata_json": "{}",
    }


def _track(track_id: int = 1) -> dict:
    return {
        "track_id": track_id,
        "start_frame": 0,
        "end_frame": 59,
        "valid_frame_count": 60,
        "gap_count": 0,
        "avg_person_confidence": 0.9,
        "avg_keypoint_confidence": 0.9,
        "valid_frame_ratio": 1.0,
        "missing_ankle_ratio": 0.0,
        "quality_status": "good",
        "include_in_export": 1,
        "exclude_reason": None,
    }


def test_worker_materializes_completed_threshold_suggestions(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    project = VideoService(repository, storage).create_project("Automatic labels")
    video = _create_video(repository, project["project_id"])
    repository.replace_tracks(video["video_id"], [_track()])
    repository.replace_threshold_suggestions(
        video["video_id"],
        project["active_threshold_profile_id"],
        [{
            "track_id": 1, "start_frame": 10, "end_frame": 30,
            "suggested_label": "falling", "confidence": 0.92,
            "triggered_conditions_json": "[\"fall_transition\"]",
            "supporting_features_json": "{}", "quality_status": "good",
            "review_status": "pending", "artifact_key": "fall-10-30",
        }],
    )
    repository.enqueue_pipeline_job(
        project["project_id"], video["video_id"], "threshold", "threshold", None, 100
    )
    worker = VideoWorker(repository, storage, tmp_path / "pose.pt", VideoFeatureService(repository, storage))
    monkeypatch.setattr(worker, "_threshold", lambda _job, progress: progress(0.9))

    completed = worker.run_once()

    assert completed and completed["status"] == "completed"
    segments = repository.list_segments(video["video_id"])
    assert [(item["start_frame"], item["end_frame"], item["label"]) for item in segments] == [
        (0, 9, "others"), (10, 30, "falling"), (31, 59, "others"),
    ]
    assert segments[1]["source_type"] == "threshold"
    assert repository.get_video(video["video_id"])["annotation_status"] == "labeled"


def test_v2_migration_normalizes_jobs_and_enforces_active_uniqueness(
    tmp_path: Path,
) -> None:
    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA_V1)
        connection.execute(
            "INSERT INTO video_schema_migrations(version) VALUES (1)"
        )
        connection.execute(
            """
            INSERT INTO video_projects(
                project_id, name, config_json, application_version
            ) VALUES ('p1', 'Legacy', '{}', '0.1')
            """
        )
        connection.execute(
            """
            INSERT INTO videos(
                video_id, project_id, filename, relative_path, file_hash,
                original_fps, canonical_fps, original_frame_count,
                canonical_frame_count, duration_seconds, width, height,
                codec, file_size
            ) VALUES (
                'v1', 'p1', 'legacy.mp4', 'raw/legacy.mp4', 'legacy',
                24, 24, 60, 60, 2.5, 100, 200, 'mp4v', 1
            )
            """
        )
        for model_id in ("m1", "m2"):
            connection.execute(
                """
                INSERT INTO external_models(
                    external_model_id, project_id, name, version,
                    artifact_path, artifact_hash, adapter_type,
                    class_map_json, feature_schema_version,
                    feature_columns_json, window_config_json,
                    compatibility_status, compatibility_errors_json,
                    metadata_json, is_active
                ) VALUES (?, 'p1', ?, '1', ?, ?, 'onnx', '{}', 'v1',
                          '[]', '{}', 'compatible', '[]', '{}', 1)
                """,
                (model_id, model_id, str(tmp_path / model_id), model_id),
            )
        connection.execute(
            """
            INSERT INTO processing_jobs(
                job_id, project_id, video_id, stage, status, priority
            ) VALUES ('legacy-model', 'p1', 'v1', 'model:m1', 'queued', 10)
            """
        )
        connection.execute(
            """
            INSERT INTO processing_jobs(
                job_id, project_id, video_id, stage, status, priority
            ) VALUES ('retained', 'p1', 'v1', 'canonicalize', 'paused', 20)
            """
        )

    repository = VideoRepository(database)
    with sqlite3.connect(database) as connection:
        columns = {
            row[1]
            for row in connection.execute("PRAGMA table_info(processing_jobs)")
        }
        indexes = {
            row[1]
            for row in connection.execute("PRAGMA index_list(processing_jobs)")
        }
    assert {"target_mode", "external_model_id"} <= columns
    assert "uq_processing_jobs_active_video" in indexes
    assert repository.get_job("legacy-model")["stage"] == "model"
    assert repository.get_job("legacy-model")["target_mode"] == "model"
    assert repository.get_job("legacy-model")["external_model_id"] == "m1"
    assert repository.get_job("legacy-model")["status"] == "cancelled"
    assert repository.get_job("retained")["status"] == "paused"
    assert sum(model["is_active"] for model in repository.list_external_models("p1")) == 1


def test_confirmed_pipeline_overwrite_clears_existing_segments(tmp_path: Path) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    service = VideoService(repository, storage)
    project = service.create_project("Overwrite")
    video = _create_video(repository, project["project_id"])
    repository.replace_tracks(video["video_id"], [_track()])
    repository.execute(
        "INSERT INTO video_segments(segment_id,video_id,track_id,start_frame,end_frame,label,annotation_version) VALUES ('old',?,1,0,10,'running',0)",
        (video["video_id"],),
    )

    service.queue_pipeline(project["project_id"], video["video_id"], "threshold", overwrite_labels=True)

    assert repository.list_segments(video["video_id"]) == []
    assert repository.get_video(video["video_id"])["annotation_status"] == "unlabeled"


def test_mode_aware_queue_uses_durable_readiness_and_pins_model(
    tmp_path: Path,
) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    service = VideoService(repository, storage)
    project = service.create_project("Processing")
    project_id = project["project_id"]
    video = _create_video(repository, project_id)
    video_id = video["video_id"]

    assert service.processing_options(project_id)["model_available"] is False
    canonical = service.queue_pipeline(
        project_id, video_id, "threshold", 1000
    )[0]
    assert canonical["stage"] == "canonicalize"
    assert service.queue_pipeline(
        project_id, video_id, "threshold", 1000
    )[0]["job_id"] == canonical["job_id"]
    repository.update_job(canonical["job_id"], status="cancelled")

    storage.write_bytes(storage.canonical_path(project_id, video_id), b"video")
    pose = service.queue_pipeline(project_id, video_id, "threshold")[0]
    assert pose["stage"] == "pose_track"
    repository.update_job(pose["job_id"], status="cancelled")

    storage.write_json(
        storage.artifact_path(project_id, "pose", video_id, "pose-v1"),
        {"frames": []},
    )
    repository.update_video(
        video_id,
        pose_cache_version="pose-v1",
        tracking_cache_version=TRACKING_CACHE_VERSION,
    )
    features = service.queue_pipeline(project_id, video_id, "threshold")[0]
    assert features["stage"] == "features"
    repository.update_job(features["job_id"], status="cancelled")

    storage.write_json(
        storage.artifact_path(
            project_id,
            "features",
            video_id,
            FEATURE_SCHEMA_VERSION,
        ),
        {"windows": []},
    )
    repository.update_video(video_id, tracking_cache_version="botsort-v1")
    stale_tracking = service.queue_pipeline(project_id, video_id, "threshold")[0]
    assert stale_tracking["stage"] == "pose_track"
    repository.update_job(stale_tracking["job_id"], status="cancelled")
    repository.update_video(video_id, tracking_cache_version=TRACKING_CACHE_VERSION)
    storage.canonical_path(project_id, video_id).unlink()
    repository.update_video(
        video_id,
        feature_cache_version=FEATURE_SCHEMA_VERSION,
        window_cache_version=WINDOW_CONFIG_VERSION,
        processing_status="failed",
    )
    threshold = service.queue_pipeline(project_id, video_id, "threshold")[0]
    assert threshold["stage"] == "threshold"
    repository.update_job(threshold["job_id"], status="cancelled")

    artifact = tmp_path / "configured.onnx"
    artifact.write_bytes(b"configured")
    model = repository.create_external_model(
        project_id,
        "configured-model",
        _model_values(artifact),
    )
    repository.activate_external_model(project_id, model["external_model_id"])
    assert service.processing_options(project_id)["model_available"] is True

    queued = service.queue_pipeline(project_id, video_id, "model", 900)[0]
    assert queued["stage"] == "model"
    assert queued["target_mode"] == "model"
    assert queued["external_model_id"] == model["external_model_id"]
    repeated = service.queue_pipeline(project_id, video_id, "model", 900)[0]
    assert repeated["job_id"] == queued["job_id"]

    replacement_artifact = tmp_path / "replacement.onnx"
    replacement_artifact.write_bytes(b"replacement")
    replacement_values = _model_values(replacement_artifact)
    replacement_values.update(
        {
            "name": "Replacement model",
            "artifact_hash": "replacement-hash",
        }
    )
    replacement = repository.create_external_model(
        project_id,
        "replacement-model",
        replacement_values,
    )
    repository.activate_external_model(
        project_id,
        replacement["external_model_id"],
    )
    assert repository.get_job(queued["job_id"])["external_model_id"] == model[
        "external_model_id"
    ]
    with pytest.raises(VideoProcessingConflictError):
        service.queue_pipeline(project_id, video_id, "threshold")
    assert repository.one(
        """
        SELECT COUNT(*) AS value FROM processing_jobs
        WHERE video_id=? AND status IN ('queued', 'running', 'paused')
        """,
        (video_id,),
    ) == {"value": 1}


def test_model_mode_requires_a_configured_active_model(tmp_path: Path) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    service = VideoService(repository, storage)
    project = service.create_project("No model")
    video = _create_video(repository, project["project_id"])

    with pytest.raises(
        ModelCompatibilityError,
        match="not configured",
    ):
        service.queue_pipeline(
            project["project_id"],
            video["video_id"],
            "model",
        )
    assert repository.list_jobs(project["project_id"]) == []


def test_concurrent_duplicate_requests_share_one_active_job(
    tmp_path: Path,
) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    project = VideoService(repository, storage).create_project("Concurrent")
    video = _create_video(repository, project["project_id"])
    barrier = Barrier(2)

    def enqueue() -> str:
        barrier.wait()
        job = repository.enqueue_pipeline_job(
            project["project_id"],
            video["video_id"],
            "canonicalize",
            "threshold",
            None,
            1000,
        )
        return str(job["job_id"])

    with ThreadPoolExecutor(max_workers=2) as executor:
        job_ids = list(executor.map(lambda _index: enqueue(), range(2)))

    assert len(set(job_ids)) == 1
    assert repository.one(
        """
        SELECT COUNT(*) AS value FROM processing_jobs
        WHERE video_id=? AND status IN ('queued', 'running', 'paused')
        """,
        (video["video_id"],),
    ) == {"value": 1}


def test_incompatible_external_model_cannot_be_activated(tmp_path: Path) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    project = VideoService(repository, storage).create_project("Models")
    artifact = tmp_path / "bad.onnx"
    artifact.write_bytes(b"bad")
    values = _model_values(artifact)
    values.update(
        {
            "compatibility_status": "incompatible",
            "compatibility_errors_json": json.dumps(["schema mismatch"]),
        }
    )
    model = repository.create_external_model(
        project["project_id"],
        "bad-model",
        values,
    )
    model_service = VideoModelService(
        repository,
        storage,
        VideoFeatureService(repository, storage),
    )

    with pytest.raises(ModelCompatibilityError, match="incompatible"):
        model_service.activate_model(
            project["project_id"],
            model["external_model_id"],
        )
    assert repository.get_external_model(model["external_model_id"])[
        "is_active"
    ] == 0


@pytest.mark.parametrize("mode", ["threshold", "model"])
def test_worker_advances_atomically_with_persisted_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    repository = VideoRepository(tmp_path / f"{mode}.sqlite3")
    storage = VideoStorageRepository(tmp_path / mode)
    service = VideoService(repository, storage)
    project = service.create_project(f"Worker {mode}")
    video = _create_video(repository, project["project_id"], mode)
    model_id = None
    if mode == "model":
        artifact = tmp_path / "worker.onnx"
        artifact.write_bytes(b"model")
        model = repository.create_external_model(
            project["project_id"],
            "worker-model",
            _model_values(artifact),
        )
        model_id = model["external_model_id"]

    repository.replace_tracks(video["video_id"], [_track()])
    repository.execute(
        """
        INSERT INTO video_segments(
            segment_id, video_id, track_id, start_frame, end_frame,
            label, annotation_version
        ) VALUES ('manual', ?, 1, 0, 10, 'others', 1)
        """,
        (video["video_id"],),
    )
    first = repository.enqueue_pipeline_job(
        project["project_id"],
        video["video_id"],
        "features",
        mode,
        model_id,
        100,
    )
    observed_models: list[str] = []

    def model_handler(job: dict, progress) -> None:
        observed_models.append(job["external_model_id"])
        progress(0.9)

    worker = VideoWorker(
        repository,
        storage,
        tmp_path / "pose.pt",
        VideoFeatureService(repository, storage),
        extra_handlers={"model": model_handler},
    )
    monkeypatch.setattr(
        worker,
        "_features",
        lambda _job, progress: progress(0.9),
    )
    monkeypatch.setattr(
        worker,
        "_threshold",
        lambda _job, progress: progress(0.9),
    )

    completed = worker.run_once()
    assert completed and completed["job_id"] == first["job_id"]
    assert completed["status"] == "completed"
    active = repository.active_job_for_video(video["video_id"])
    assert active and active["stage"] == mode
    assert active["target_mode"] == mode
    assert active["external_model_id"] == model_id
    assert repository.list_segments(video["video_id"])[0]["segment_id"] == "manual"

    final = worker.run_once()
    assert final and final["status"] == "completed"
    assert repository.active_job_for_video(video["video_id"]) is None
    assert observed_models == ([model_id] if model_id else [])
    assert repository.list_segments(video["video_id"])[0]["label"] == "others"


def test_pose_replacement_preserves_manual_segments_as_labeled(
    tmp_path: Path,
) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    service = VideoService(repository, storage)
    project = service.create_project("Pose refresh")
    video = _create_video(repository, project["project_id"])
    video_id = video["video_id"]
    repository.replace_tracks(video_id, [_track()])
    repository.execute(
        """
        INSERT INTO video_segments(
            segment_id, video_id, track_id, start_frame, end_frame,
            label, annotation_version
        ) VALUES ('kept', ?, 1, 5, 20, 'falling', 3)
        """,
        (video_id,),
    )
    repository.update_video(
        video_id,
        annotation_revision=3,
        annotation_status="approved",
        is_approved=1,
        approval_revision=3,
        feature_cache_version="old",
        threshold_cache_version="old",
        window_cache_version="old",
    )

    repository.replace_tracks(
        video_id,
        [_track()],
        invalidate_derived=True,
    )

    segment = repository.list_segments(video_id)[0]
    refreshed = repository.get_video(video_id)
    assert segment["segment_id"] == "kept"
    assert segment["label"] == "falling"
    assert segment["quality_status"] == "good"
    assert refreshed["annotation_revision"] == 3
    assert refreshed["annotation_status"] == "approved"
    assert refreshed["is_approved"] == 1
    assert refreshed["feature_cache_version"] is None
    assert refreshed["threshold_cache_version"] is None
    assert refreshed["window_cache_version"] is None
