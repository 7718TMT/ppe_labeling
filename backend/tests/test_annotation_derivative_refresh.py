"""Contracts for revision-aware annotation derivative refresh jobs."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_video_service
from backend.app.domain.video import FEATURE_SCHEMA_VERSION, WINDOW_CONFIG_VERSION
from backend.app.domain.errors import VideoProcessingConflictError
from backend.app.main import create_app
from backend.app.repositories.video_db import (
    ANNOTATION_DERIVATIVE_STAGE,
    VideoRepository,
)
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_annotation_service import VideoAnnotationService
from backend.app.services.video_feature_service import VideoFeatureService
from backend.app.services.video_service import VideoService
from backend.app.services.video_worker import VideoWorker


def _track() -> dict[str, object]:
    """Build one stable worker track for a 60-frame test video."""

    return {
        "track_id": 1,
        "start_frame": 0,
        "end_frame": 59,
        "valid_frame_count": 60,
        "gap_count": 0,
        "avg_person_confidence": 0.95,
        "avg_keypoint_confidence": 0.9,
        "valid_frame_ratio": 1.0,
        "missing_ankle_ratio": 0.0,
        "quality_status": "good",
        "include_in_export": 1,
        "exclude_reason": None,
    }


def _pose_frames() -> list[dict[str, object]]:
    """Return deterministic pose data needed by the real feature extractor."""

    frames: list[dict[str, object]] = []
    for frame_index in range(60):
        keypoints = [[50.0, 80.0] for _ in range(17)]
        keypoints[0] = [50.0, 20.0]
        keypoints[5], keypoints[6] = [40.0, 40.0], [60.0, 40.0]
        keypoints[11], keypoints[12] = [45.0, 100.0], [55.0, 100.0]
        keypoints[15], keypoints[16] = [45.0, 190.0], [55.0, 190.0]
        frames.append(
            {
                "frame_index": frame_index,
                "tracks": [
                    {
                        "track_id": 1,
                        "bbox": [0.0, 0.0, 100.0, 200.0],
                        "keypoints": keypoints,
                        "keypoint_scores": [0.9] * 17,
                        "person_confidence": 0.95,
                    }
                ],
            }
        )
    return frames


def _ready_video(
    tmp_path: Path,
    name: str = "derivatives",
) -> tuple[
    VideoRepository,
    VideoStorageRepository,
    VideoService,
    dict[str, object],
    dict[str, object],
]:
    """Create a pose-ready video with one track and valid pose artifact."""

    repository = VideoRepository(tmp_path / f"{name}.sqlite3")
    storage = VideoStorageRepository(tmp_path / name)
    service = VideoService(repository, storage)
    project = service.create_project("Derivative refresh")
    video = repository.create_video(
        str(project["project_id"]),
        {
            "filename": f"{name}.mp4",
            "relative_path": f"raw/{name}.mp4",
            "file_hash": name,
            "original_fps": 24,
            "canonical_fps": 24,
            "original_frame_count": 60,
            "canonical_frame_count": 60,
            "duration_seconds": 2.5,
            "width": 100,
            "height": 200,
            "codec": "mp4v",
            "file_size": 1,
            "pose_cache_version": "pose-v1",
            "tracking_cache_version": "tracking-v1",
        },
    )
    repository.replace_tracks(str(video["video_id"]), [_track()])
    storage.write_json(
        storage.artifact_path(
            str(project["project_id"]),
            "pose",
            str(video["video_id"]),
            "pose-v1",
        ),
        {"frames": _pose_frames()},
    )
    return repository, storage, service, project, video


def test_annotation_derivative_endpoint_queues_a_dedicated_stage(
    tmp_path: Path,
) -> None:
    """The public endpoint never returns a Threshold/model suggestion job."""

    repository, _storage, service, project, video = _ready_video(tmp_path)
    app = create_app()
    app.dependency_overrides[get_video_service] = lambda: service

    with TestClient(app) as client:
        response = client.post(
            "/api/v1/video-projects/"
            f"{project['project_id']}/videos/{video['video_id']}"
            "/annotation-derivatives/refresh"
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["requested_revision"] == 0
    assert payload["job"]["stage"] == ANNOTATION_DERIVATIVE_STAGE
    assert repository.active_job_for_video(str(video["video_id"]))["stage"] == (
        ANNOTATION_DERIVATIVE_STAGE
    )


def test_delete_last_segment_refreshes_derivatives_without_rematerializing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A blank annotation remains blank after its windows/features are rebuilt."""

    repository, storage, service, project, video = _ready_video(tmp_path)
    video_id = str(video["video_id"])
    annotation_service = VideoAnnotationService(repository, storage)
    saved = annotation_service.save_segment(video_id, 1, 0, 59, "running", 0)
    annotation_service.delete_segment(
        video_id,
        str(saved["segment"]["segment_id"]),
        int(saved["revision"]),
    )
    assert repository.list_segments(video_id) == []

    profile_id = str(repository.get_project(str(project["project_id"]))[
        "active_threshold_profile_id"
    ])
    repository.replace_threshold_suggestions(
        video_id,
        profile_id,
        [
            {
                "track_id": 1,
                "start_frame": 12,
                "end_frame": 48,
                "suggested_label": "running",
                "confidence": 0.95,
                "triggered_conditions_json": "[\"test\"]",
                "supporting_features_json": "{}",
                "quality_status": "good",
                "review_status": "pending",
                "artifact_key": "must-not-materialize",
            }
        ],
    )

    # The segment delete itself persisted a new derivative intent; no frontend
    # timer or follow-up HTTP request is needed to keep artifacts current.
    queued = repository.active_job_for_video(video_id)
    assert queued and queued["stage"] == ANNOTATION_DERIVATIVE_STAGE
    assert queued["annotation_revision"] == 1
    worker = VideoWorker(
        repository,
        storage,
        tmp_path / "pose.pt",
        VideoFeatureService(repository, storage),
    )

    def must_not_materialize(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("Derivative refresh must not materialize suggestions")

    monkeypatch.setattr(worker.annotation_service, "materialize_suggestions", must_not_materialize)
    stale = worker.run_once()
    completed = worker.run_once()

    assert stale and stale["status"] == "completed"
    assert completed and completed["status"] == "completed"
    assert repository.list_segments(video_id) == []
    assert repository.list_suggestions("threshold_suggestions", video_id)[0][
        "review_status"
    ] == "pending"
    windows = repository.list_windows(video_id)
    assert windows and all(window["label"] is None for window in windows)
    refreshed_video = repository.get_video(video_id)
    assert refreshed_video["window_cache_version"] == WINDOW_CONFIG_VERSION
    assert refreshed_video["feature_cache_version"] == FEATURE_SCHEMA_VERSION
    assert refreshed_video["threshold_cache_version"] is None
    assert repository.one(
        "SELECT COUNT(*) AS value FROM annotation_derivative_refreshes WHERE video_id=?",
        (video_id,),
    ) == {"value": 0}


def test_stale_suggestion_job_cannot_rematerialize_after_last_segment_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A manual delete wins when an older suggestion job finishes later."""

    repository, storage, service, project, video = _ready_video(tmp_path)
    project_id = str(project["project_id"])
    video_id = str(video["video_id"])
    profile_id = str(
        repository.get_project(project_id)["active_threshold_profile_id"]
    )
    repository.replace_threshold_suggestions(
        video_id,
        profile_id,
        [
            {
                "track_id": 1,
                "start_frame": 12,
                "end_frame": 48,
                "suggested_label": "running",
                "confidence": 0.95,
                "triggered_conditions_json": "[\"test\"]",
                "supporting_features_json": "{}",
                "quality_status": "good",
                "review_status": "pending",
                "artifact_key": "stale-suggestion",
            }
        ],
    )
    suggestion_job = repository.enqueue_pipeline_job(
        project_id,
        video_id,
        "threshold",
        "threshold",
        None,
    )
    assert suggestion_job["annotation_revision"] == 0
    annotations = VideoAnnotationService(repository, storage)
    saved = annotations.save_segment(video_id, 1, 0, 59, "others", 0)
    annotations.delete_segment(
        video_id,
        str(saved["segment"]["segment_id"]),
        int(saved["revision"]),
    )
    deferred = service.refresh_annotation_derivatives(project_id, video_id)
    assert deferred["status"] == "deferred"
    assert deferred["requested_revision"] == 2

    worker = VideoWorker(
        repository,
        storage,
        tmp_path / "pose.pt",
        VideoFeatureService(repository, storage),
    )
    monkeypatch.setattr(worker, "_threshold", lambda _job, progress: progress(0.9))

    def must_not_materialize(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("A stale suggestion job must not recreate segments")

    monkeypatch.setattr(worker.annotation_service, "materialize_suggestions", must_not_materialize)
    completed = worker.run_once()

    assert completed and completed["status"] == "completed"
    assert repository.get_job(str(suggestion_job["job_id"]))["status"] == "completed"
    assert repository.list_segments(video_id) == []
    derivative = repository.active_job_for_video(video_id)
    assert derivative and derivative["stage"] == ANNOTATION_DERIVATIVE_STAGE
    assert derivative["annotation_revision"] == 2


def test_deferred_refresh_waits_for_the_final_suggestion_stage(
    tmp_path: Path,
) -> None:
    """A successful suggestion job promotes, rather than absorbs, an edit."""

    repository, _storage, service, project, video = _ready_video(tmp_path)
    project_id = str(project["project_id"])
    video_id = str(video["video_id"])
    suggestion_job = repository.enqueue_pipeline_job(
        project_id,
        video_id,
        "threshold",
        "threshold",
        None,
    )
    assert service.refresh_annotation_derivatives(project_id, video_id)["status"] == (
        "deferred"
    )

    claimed = repository.claim_job("test-worker")
    assert claimed and claimed["job_id"] == suggestion_job["job_id"]
    completed, successor = repository.complete_job_and_enqueue_next(
        str(suggestion_job["job_id"]),
        None,
    )

    assert completed["status"] == "completed"
    assert successor and successor["stage"] == ANNOTATION_DERIVATIVE_STAGE
    assert successor["annotation_revision"] == 0


def test_derivative_job_requeues_when_the_annotation_revision_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A queued stale revision cannot publish label-bearing feature artifacts."""

    repository, storage, service, project, video = _ready_video(tmp_path)
    project_id = str(project["project_id"])
    video_id = str(video["video_id"])
    queued = service.refresh_annotation_derivatives(project_id, video_id)
    assert queued["job"]["annotation_revision"] == 0
    VideoAnnotationService(repository, storage).save_segment(
        video_id,
        1,
        0,
        59,
        "others",
        0,
    )
    worker = VideoWorker(
        repository,
        storage,
        tmp_path / "pose.pt",
        VideoFeatureService(repository, storage),
    )

    def must_not_generate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("A stale derivative job must not generate artifacts")

    monkeypatch.setattr(worker.feature_service, "generate_windows", must_not_generate)
    monkeypatch.setattr(worker.feature_service, "extract_features", must_not_generate)
    completed = worker.run_once()

    assert completed and completed["status"] == "completed"
    successor = repository.active_job_for_video(video_id)
    assert successor and successor["stage"] == ANNOTATION_DERIVATIVE_STAGE
    assert successor["annotation_revision"] == 1
    assert repository.get_video(video_id)["feature_cache_version"] is None


def test_manual_track_mutation_requeues_derivatives_without_refresh_endpoint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Worker edits advance the same derivative revision as segment edits."""

    repository, storage, service, project, video = _ready_video(tmp_path)
    project_id = str(project["project_id"])
    video_id = str(video["video_id"])
    queued = service.refresh_annotation_derivatives(project_id, video_id)
    assert queued["job"]["annotation_revision"] == 0
    repository.update_video(
        video_id,
        is_approved=1,
        approval_revision=0,
    )

    VideoAnnotationService(repository, storage).set_track_inclusion(
        video_id,
        1,
        False,
        "manual exclusion",
    )

    changed_video = repository.get_video(video_id)
    assert changed_video["annotation_revision"] == 1
    assert changed_video["is_approved"] == 0
    assert repository.one(
        "SELECT requested_revision FROM annotation_derivative_refreshes WHERE video_id=?",
        (video_id,),
    ) == {"requested_revision": 1}
    worker = VideoWorker(
        repository,
        storage,
        tmp_path / "pose.pt",
        VideoFeatureService(repository, storage),
    )

    def must_not_generate(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("A stale derivative job must not generate artifacts")

    monkeypatch.setattr(worker.feature_service, "generate_windows", must_not_generate)
    monkeypatch.setattr(worker.feature_service, "extract_features", must_not_generate)
    completed = worker.run_once()

    assert completed and completed["status"] == "completed"
    successor = repository.active_job_for_video(video_id)
    assert successor and successor["stage"] == ANNOTATION_DERIVATIVE_STAGE
    assert successor["annotation_revision"] == 1
    assert len(
        [
            job
            for job in repository.list_jobs(project_id)
            if job["stage"] == ANNOTATION_DERIVATIVE_STAGE
            and job["status"] in {"queued", "running", "paused"}
        ]
    ) == 1


def test_atomic_materialization_rolls_back_all_segments_on_interruption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A write failure cannot leave a partially materialized suggestion set."""

    repository, _storage, _service, project, video = _ready_video(tmp_path)
    project_id = str(project["project_id"])
    video_id = str(video["video_id"])
    profile_id = str(repository.get_project(project_id)["active_threshold_profile_id"])
    repository.replace_threshold_suggestions(
        video_id,
        profile_id,
        [
            {
                "track_id": 1,
                "start_frame": 12,
                "end_frame": 48,
                "suggested_label": "running",
                "confidence": 0.95,
                "triggered_conditions_json": "[\"test\"]",
                "supporting_features_json": "{}",
                "quality_status": "good",
                "review_status": "pending",
                "artifact_key": "atomic-materialization",
            }
        ],
    )
    suggestion_id = repository.list_suggestions("threshold_suggestions", video_id)[0][
        "suggestion_id"
    ]
    original_record_history = repository._record_history
    calls = 0

    def interrupt_after_first_history(*args: object) -> None:
        nonlocal calls
        original_record_history(*args)
        calls += 1
        if calls == 1:
            raise RuntimeError("synthetic interleaving failure")

    monkeypatch.setattr(repository, "_record_history", interrupt_after_first_history)
    with pytest.raises(RuntimeError, match="synthetic interleaving failure"):
        repository.materialize_suggestion_segments(
            video_id,
            "threshold_suggestions",
            [str(suggestion_id)],
            [
                {
                    "track_id": 1,
                    "start_frame": 0,
                    "end_frame": 11,
                    "label": "others",
                    "source_type": "auto_default",
                    "source_id": None,
                },
                {
                    "track_id": 1,
                    "start_frame": 12,
                    "end_frame": 48,
                    "label": "running",
                    "source_type": "threshold",
                    "source_id": str(suggestion_id),
                },
                {
                    "track_id": 1,
                    "start_frame": 49,
                    "end_frame": 59,
                    "label": "others",
                    "source_type": "auto_default",
                    "source_id": None,
                },
            ],
            expected_revision=0,
        )

    assert repository.list_segments(video_id) == []
    assert repository.list_history(video_id) == []
    assert repository.get_video(video_id)["annotation_revision"] == 0
    assert repository.list_suggestions("threshold_suggestions", video_id)[0][
        "review_status"
    ] == "pending"


def test_atomic_materialization_persists_derivative_maintenance(
    tmp_path: Path,
) -> None:
    """Automatic ground truth persists its export refresh in the same commit."""

    repository, storage, _service, project, video = _ready_video(tmp_path)
    project_id = str(project["project_id"])
    video_id = str(video["video_id"])
    profile_id = str(repository.get_project(project_id)["active_threshold_profile_id"])
    repository.replace_threshold_suggestions(
        video_id,
        profile_id,
        [
            {
                "track_id": 1,
                "start_frame": 12,
                "end_frame": 48,
                "suggested_label": "running",
                "confidence": 0.95,
                "triggered_conditions_json": "[\"test\"]",
                "supporting_features_json": "{}",
                "quality_status": "good",
                "review_status": "pending",
                "artifact_key": "no-maintenance-loop",
            }
        ],
    )

    created = VideoAnnotationService(repository, storage).materialize_suggestions(
        video_id,
        "threshold",
        expected_revision=0,
    )

    assert len(created) == 3
    maintenance = repository.active_job_for_video(video_id)
    assert maintenance and maintenance["stage"] == ANNOTATION_DERIVATIVE_STAGE
    assert maintenance["annotation_revision"] == 3
    assert repository.one(
        "SELECT requested_revision FROM annotation_derivative_refreshes WHERE video_id=?",
        (video_id,),
    ) == {"requested_revision": 3}


def test_auto_materialization_queues_durable_derivative_successor(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The final suggestion stage delegates export artifacts to a durable job."""

    repository, storage, _service, project, video = _ready_video(tmp_path)
    project_id = str(project["project_id"])
    video_id = str(video["video_id"])
    profile_id = str(repository.get_project(project_id)["active_threshold_profile_id"])
    repository.replace_threshold_suggestions(
        video_id,
        profile_id,
        [
            {
                "track_id": 1,
                "start_frame": 0,
                "end_frame": 59,
                "suggested_label": "running",
                "confidence": 0.95,
                "triggered_conditions_json": "[\"test\"]",
                "supporting_features_json": "{}",
                "quality_status": "good",
                "review_status": "pending",
                "artifact_key": "durable-auto-feature-refresh",
            }
        ],
    )
    job = repository.enqueue_pipeline_job(
        project_id,
        video_id,
        "threshold",
        "threshold",
        None,
    )
    worker = VideoWorker(
        repository,
        storage,
        tmp_path / "pose.pt",
        VideoFeatureService(repository, storage),
    )
    # The suggestion row above represents completed inference. This isolates
    # the final materialization/export-derivative contract from scoring rules.
    monkeypatch.setattr(worker, "_threshold", lambda _job, progress: progress(0.9))

    completed = worker.run_once()

    assert completed and completed["status"] == "completed"
    assert repository.get_job(str(job["job_id"]))["status"] == "completed"
    maintenance = repository.active_job_for_video(video_id)
    assert maintenance and maintenance["stage"] == ANNOTATION_DERIVATIVE_STAGE
    assert maintenance["annotation_revision"] == 1
    assert repository.get_video(video_id)["feature_cache_version"] is None

    derivative_completed = worker.run_once()

    assert derivative_completed and derivative_completed["status"] == "completed"
    refreshed = repository.get_video(video_id)
    assert refreshed["window_cache_version"] == WINDOW_CONFIG_VERSION
    assert refreshed["feature_cache_version"] == FEATURE_SCHEMA_VERSION
    windows = repository.list_windows(video_id)
    assert windows and all(window["label"] == "running" for window in windows)
    records = worker.feature_service.feature_range(video_id)
    assert records and all(record["label"] == "running" for record in records)
    assert repository.active_job_for_video(video_id) is None
    assert repository.one(
        "SELECT COUNT(*) AS value FROM annotation_derivative_refreshes WHERE video_id=?",
        (video_id,),
    ) == {"value": 0}


def test_crash_after_auto_materialization_keeps_durable_derivative_intent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A worker crash after label commit cannot strand stale export artifacts."""

    repository, storage, _service, project, video = _ready_video(tmp_path)
    project_id = str(project["project_id"])
    video_id = str(video["video_id"])
    profile_id = str(repository.get_project(project_id)["active_threshold_profile_id"])
    repository.replace_threshold_suggestions(
        video_id,
        profile_id,
        [
            {
                "track_id": 1,
                "start_frame": 0,
                "end_frame": 59,
                "suggested_label": "running",
                "confidence": 0.95,
                "triggered_conditions_json": "[\"test\"]",
                "supporting_features_json": "{}",
                "quality_status": "good",
                "review_status": "pending",
                "artifact_key": "crash-after-materialization",
            }
        ],
    )
    job = repository.enqueue_pipeline_job(
        project_id,
        video_id,
        "threshold",
        "threshold",
        None,
    )
    worker = VideoWorker(
        repository,
        storage,
        tmp_path / "pose.pt",
        VideoFeatureService(repository, storage),
    )
    monkeypatch.setattr(worker, "_threshold", lambda _job, progress: progress(0.9))
    original_complete = repository.complete_job_and_enqueue_next

    class SimulatedWorkerCrash(BaseException):
        """Bypass ``run_once`` exception handling like a terminated process."""

    def crash_before_terminal_commit(*_args: object, **_kwargs: object) -> None:
        raise SimulatedWorkerCrash()

    monkeypatch.setattr(
        repository,
        "complete_job_and_enqueue_next",
        crash_before_terminal_commit,
    )
    with pytest.raises(SimulatedWorkerCrash):
        worker.run_once()

    assert repository.get_job(str(job["job_id"]))["status"] == "running"
    assert repository.list_segments(video_id)
    assert repository.one(
        "SELECT requested_revision FROM annotation_derivative_refreshes WHERE video_id=?",
        (video_id,),
    ) == {"requested_revision": 1}

    monkeypatch.setattr(
        repository,
        "complete_job_and_enqueue_next",
        original_complete,
    )
    repository.execute(
        "UPDATE processing_jobs SET heartbeat_at='2000-01-01' WHERE job_id=?",
        (job["job_id"],),
    )
    assert worker.recover() == 1
    resumed = worker.run_once()
    assert resumed and resumed["status"] == "completed"
    maintenance = repository.active_job_for_video(video_id)
    assert maintenance and maintenance["stage"] == ANNOTATION_DERIVATIVE_STAGE
    assert maintenance["annotation_revision"] == 1

    derivative_completed = worker.run_once()
    assert derivative_completed and derivative_completed["status"] == "completed"
    assert repository.get_video(video_id)["feature_cache_version"] == (
        FEATURE_SCHEMA_VERSION
    )
    assert repository.active_job_for_video(video_id) is None


def test_confirmed_suggestion_overwrite_supersedes_queued_derivatives(
    tmp_path: Path,
) -> None:
    """Explicit suggestion generation wins over queued maintenance work."""

    repository, storage, service, project, video = _ready_video(tmp_path)
    project_id = str(project["project_id"])
    video_id = str(video["video_id"])
    saved = VideoAnnotationService(repository, storage).save_segment(
        video_id,
        1,
        0,
        59,
        "others",
        0,
    )
    maintenance = repository.active_job_for_video(video_id)
    assert maintenance and maintenance["stage"] == ANNOTATION_DERIVATIVE_STAGE

    queued = service.queue_pipeline(
        project_id,
        video_id,
        "threshold",
        overwrite_labels=True,
    )[0]

    assert repository.get_job(str(maintenance["job_id"]))["status"] == "cancelled"
    assert queued["stage"] != ANNOTATION_DERIVATIVE_STAGE
    assert queued["target_mode"] == "threshold"
    assert queued["annotation_revision"] == int(saved["revision"]) + 1
    assert repository.list_segments(video_id) == []
    assert repository.one(
        "SELECT COUNT(*) AS value FROM annotation_derivative_refreshes WHERE video_id=?",
        (video_id,),
    ) == {"value": 0}


def test_confirmed_overwrite_preserves_labels_when_derivatives_are_running(
    tmp_path: Path,
) -> None:
    """A running maintenance job blocks overwrite before any labels are cleared."""

    repository, storage, service, project, video = _ready_video(tmp_path)
    project_id = str(project["project_id"])
    video_id = str(video["video_id"])
    saved = VideoAnnotationService(repository, storage).save_segment(
        video_id,
        1,
        0,
        59,
        "others",
        0,
    )
    running = repository.claim_job("derivative-worker")
    assert running and running["stage"] == ANNOTATION_DERIVATIVE_STAGE

    with pytest.raises(VideoProcessingConflictError, match="derivative refresh is running"):
        service.queue_pipeline(
            project_id,
            video_id,
            "threshold",
            overwrite_labels=True,
        )

    assert repository.get_job(str(running["job_id"]))["status"] == "running"
    assert repository.list_segments(video_id)[0]["segment_id"] == saved["segment"][
        "segment_id"
    ]


@pytest.mark.parametrize("terminal_status", ["failed", "cancelled"])
def test_deferred_refresh_is_promoted_once_after_terminal_suggestion_job(
    tmp_path: Path,
    terminal_status: str,
) -> None:
    """Failed or cancelled suggestion work cannot strand a pending edit refresh."""

    repository, _storage, service, project, video = _ready_video(
        tmp_path,
        terminal_status,
    )
    project_id = str(project["project_id"])
    video_id = str(video["video_id"])
    suggestion_job = repository.enqueue_pipeline_job(
        project_id,
        video_id,
        "threshold",
        "threshold",
        None,
    )
    deferred = service.refresh_annotation_derivatives(project_id, video_id)
    assert deferred == {
        "requested_revision": 0,
        "status": "deferred",
        "job": None,
    }

    if terminal_status == "cancelled":
        service.control_job(str(suggestion_job["job_id"]), "cancel")
    else:
        repository.update_job(
            str(suggestion_job["job_id"]),
            status="failed",
            error_message="synthetic inference failure",
        )

    derivative_jobs = [
        job
        for job in repository.list_jobs(project_id)
        if job["stage"] == ANNOTATION_DERIVATIVE_STAGE
    ]
    assert len(derivative_jobs) == 1
    assert derivative_jobs[0]["status"] == "queued"
    assert derivative_jobs[0]["annotation_revision"] == 0
    repeated = service.refresh_annotation_derivatives(project_id, video_id)
    assert repeated["status"] == "already_queued"
    assert repeated["job"]["job_id"] == derivative_jobs[0]["job_id"]
    assert len(
        [
            job
            for job in repository.list_jobs(project_id)
            if job["stage"] == ANNOTATION_DERIVATIVE_STAGE
        ]
    ) == 1
