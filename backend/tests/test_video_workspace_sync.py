"""Focused contracts for durable video-workspace synchronization."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.controllers.video.controller import _sse_message
from backend.app.api.dependencies import (
    get_video_annotation_service,
    get_video_export_service,
    get_video_feature_service,
    get_video_model_service,
    get_video_service,
    get_video_workspace_sync_service,
)
from backend.app.main import create_app
from backend.app.repositories.video_db import SCHEMA_V1, VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_annotation_service import VideoAnnotationService
from backend.app.services.video_export_service import VideoExportService
from backend.app.services.video_feature_service import VideoFeatureService
from backend.app.services.video_model_service import VideoModelService
from backend.app.services.video_service import VideoService
from backend.app.services.video_workspace_sync_service import VideoWorkspaceSyncService


def _video_values(file_hash: str = "workspace-video") -> dict[str, object]:
    return {
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
    }


def _track() -> dict[str, object]:
    return {
        "track_id": 1,
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


def test_v4_migration_adds_workspace_outbox_and_derivative_state(
    tmp_path: Path,
) -> None:
    """A v1 database upgrades without rebuilding its existing tables."""

    database = tmp_path / "legacy.sqlite3"
    with sqlite3.connect(database) as connection:
        connection.executescript(SCHEMA_V1)
        connection.execute("INSERT INTO video_schema_migrations(version) VALUES (1)")

    VideoRepository(database)

    with sqlite3.connect(database) as connection:
        version = connection.execute(
            "SELECT MAX(version) FROM video_schema_migrations"
        ).fetchone()[0]
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
        }
        indexes = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            )
        }

    assert version == 4
    assert "video_workspace_events" in tables
    assert "annotation_derivative_refreshes" in tables
    assert "idx_workspace_events_project_event" in indexes
    with sqlite3.connect(database) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(processing_jobs)")
        }
    assert "annotation_revision" in columns


def test_workspace_events_are_transactional_and_progress_is_coalesced(
    tmp_path: Path,
) -> None:
    """Visible record changes emit small durable events, not heartbeat spam."""

    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    project = VideoService(repository, storage).create_project("Workspace")
    project_id = str(project["project_id"])
    video = repository.create_video(project_id, _video_values())
    video_id = str(video["video_id"])

    video_event = repository.workspace_event_changes(project_id, 0)["events"][-1]
    assert video_event["event_type"] == "video.changed"
    assert video_event["payload"]["video"]["video_id"] == video_id

    job = repository.enqueue_pipeline_job(
        project_id,
        video_id,
        "canonicalize",
        "threshold",
        None,
    )
    claimed = repository.claim_job("test-worker")
    assert claimed and claimed["job_id"] == job["job_id"]
    cursor = repository.latest_workspace_event_id(project_id)

    repository.update_job(str(job["job_id"]), progress=0.005)
    assert repository.workspace_event_changes(project_id, cursor)["events"] == []
    repository.update_job(str(job["job_id"]), progress=0.02)
    progress_events = repository.workspace_event_changes(project_id, cursor)["events"]
    assert len(progress_events) == 1
    assert progress_events[0]["event_type"] == "job.changed"
    assert progress_events[0]["payload"]["job"]["progress"] == pytest.approx(0.02)

    track_cursor = repository.latest_workspace_event_id(project_id)
    repository.replace_tracks(video_id, [_track()])
    track_events = repository.workspace_event_changes(project_id, track_cursor)[
        "events"
    ]
    assert track_events[0]["event_type"] == "tracks.changed"
    assert track_events[0]["payload"] == {
        "annotation_revision": 0,
        "annotation_status": "unlabeled",
        "approval_revision": None,
        "is_approved": False,
        "reason": "tracks_replaced",
        "video_id": video_id,
    }
    annotation_cursor = repository.latest_workspace_event_id(project_id)
    annotation = VideoAnnotationService(repository, storage)
    annotation.save_segment(video_id, 1, 0, 20, "others", 0)
    annotation_events = repository.workspace_event_changes(
        project_id, annotation_cursor
    )["events"]
    assert [event["event_type"] for event in annotation_events] == [
        "annotation.changed"
    ]
    assert annotation_events[0]["payload"] == {
        "annotation_revision": 1,
        "annotation_status": "labeled",
        "approval_revision": None,
        "is_approved": False,
        "reason": "segment_create",
        "video_id": video_id,
    }

    export_cursor = repository.latest_workspace_event_id(project_id)
    export = repository.create_export(project_id)
    repository.update_export(str(export["export_id"]), status="running")
    export_events = repository.workspace_event_changes(project_id, export_cursor)[
        "events"
    ]
    assert [event["event_type"] for event in export_events] == [
        "export.changed",
        "export.changed",
    ]
    assert export_events[-1]["payload"]["export"] == {
        "artifact_path": None,
        "created_at": export["created_at"],
        "export_id": export["export_id"],
        "finished_at": None,
        "job_id": None,
        "project_id": project_id,
        "status": "running",
        "validation": [],
    }


def test_composed_track_edits_publish_compact_track_refreshes(
    tmp_path: Path,
) -> None:
    """Remote workspaces learn every manual worker-list shape change."""

    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    project = VideoService(repository, storage).create_project("Track events")
    project_id = str(project["project_id"])
    video = repository.create_video(project_id, _video_values())
    video_id = str(video["video_id"])
    repository.replace_tracks(
        video_id,
        [
            {**_track(), "track_id": 1},
            {**_track(), "track_id": 2},
        ],
    )
    annotation = VideoAnnotationService(repository, storage)

    def track_events_after(cursor: int) -> list[dict]:
        return [
            event
            for event in repository.workspace_event_changes(project_id, cursor)["events"]
            if event["event_type"] == "tracks.changed"
        ]

    cursor = repository.latest_workspace_event_id(project_id)
    annotation.merge_tracks(video_id, 1, 2)
    events = track_events_after(cursor)
    assert len(events) == 1
    assert events[0]["payload"] == {
        "annotation_revision": 1,
        "annotation_status": "unlabeled",
        "approval_revision": None,
        "is_approved": False,
        "reason": "tracks_merged",
        "video_id": video_id,
    }

    cursor = repository.latest_workspace_event_id(project_id)
    annotation.split_track(video_id, 1, 30)
    events = track_events_after(cursor)
    assert len(events) == 1
    assert events[0]["payload"]["reason"] == "track_split"
    assert events[0]["payload"]["annotation_revision"] == 2

    cursor = repository.latest_workspace_event_id(project_id)
    annotation.set_track_inclusion(video_id, 1, False, "manual exclusion")
    events = track_events_after(cursor)
    assert len(events) == 1
    assert events[0]["payload"]["reason"] == "track_inclusion_changed"
    assert events[0]["payload"]["annotation_revision"] == 3

    cursor = repository.latest_workspace_event_id(project_id)
    annotation.delete_track(video_id, 2)
    events = track_events_after(cursor)
    assert len(events) == 1
    assert events[0]["payload"]["reason"] == "track_deleted"
    assert events[0]["payload"]["annotation_revision"] == 4


def test_multi_merge_publishes_one_track_refresh(tmp_path: Path) -> None:
    """A multi-merge is a single remote refresh instead of one per source."""

    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    project = VideoService(repository, storage).create_project("Multi merge")
    project_id = str(project["project_id"])
    video = repository.create_video(project_id, _video_values())
    video_id = str(video["video_id"])
    repository.replace_tracks(
        video_id,
        [{**_track(), "track_id": track_id} for track_id in (1, 2, 3)],
    )
    cursor = repository.latest_workspace_event_id(project_id)

    VideoAnnotationService(repository, storage).merge_multiple_tracks(
        video_id,
        [1, 2, 3],
    )

    events = [
        event
        for event in repository.workspace_event_changes(project_id, cursor)["events"]
        if event["event_type"] == "tracks.changed"
    ]
    assert len(events) == 1
    assert events[0]["payload"]["reason"] == "tracks_merged"


def test_multi_merge_rolls_back_every_source_with_its_revision_and_events(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failure at finalization cannot leave a partially merged worker set."""

    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    project = VideoService(repository, storage).create_project("Atomic multi merge")
    project_id = str(project["project_id"])
    video = repository.create_video(project_id, _video_values())
    video_id = str(video["video_id"])
    repository.replace_tracks(
        video_id,
        [{**_track(), "track_id": track_id} for track_id in (1, 2, 3)],
    )
    cursor = repository.latest_workspace_event_id(project_id)

    def fail_track_event(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("synthetic finalization failure")

    monkeypatch.setattr(repository, "_emit_tracks_changed", fail_track_event)
    with pytest.raises(RuntimeError, match="synthetic finalization failure"):
        VideoAnnotationService(repository, storage).merge_multiple_tracks(
            video_id,
            [1, 2, 3],
        )

    assert [track["track_id"] for track in repository.list_tracks(video_id)] == [
        1,
        2,
        3,
    ]
    assert repository.get_video(video_id)["annotation_revision"] == 0
    assert repository.workspace_event_changes(project_id, cursor)["events"] == []
    assert repository.one(
        "SELECT COUNT(*) AS value FROM annotation_derivative_refreshes WHERE video_id=?",
        (video_id,),
    ) == {"value": 0}


def test_materialized_suggestions_publish_one_annotation_refresh(tmp_path: Path) -> None:
    """Automatic labels do not create one SSE refresh per generated segment."""

    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    project = VideoService(repository, storage).create_project("Suggestions")
    project_id = str(project["project_id"])
    video = repository.create_video(project_id, _video_values())
    video_id = str(video["video_id"])
    repository.replace_tracks(video_id, [_track()])
    repository.replace_threshold_suggestions(
        video_id,
        str(project["active_threshold_profile_id"]),
        [
            {
                "track_id": 1,
                "start_frame": 10,
                "end_frame": 30,
                "suggested_label": "falling",
                "confidence": 0.9,
                "triggered_conditions_json": "[\"fall\"]",
                "supporting_features_json": "{}",
                "quality_status": "good",
                "review_status": "pending",
                "artifact_key": "fall-10-30",
            }
        ],
    )
    cursor = repository.latest_workspace_event_id(project_id)

    created = VideoAnnotationService(repository, storage).materialize_suggestions(
        video_id, "threshold"
    )

    events = repository.workspace_event_changes(project_id, cursor)["events"]
    assert len(created) == 3
    assert [event["event_type"] for event in events] == ["annotation.changed"]
    assert events[0]["payload"]["reason"] == "suggestions_materialized"
    assert events[0]["payload"]["annotation_revision"] == 3


def test_stale_workspace_cursor_requires_snapshot_resync(tmp_path: Path) -> None:
    """A cursor older than retained outbox history never returns a partial delta."""

    repository = VideoRepository(tmp_path / "state.sqlite3")
    project = VideoService(
        repository, VideoStorageRepository(tmp_path / "storage")
    ).create_project("Retention")
    project_id = str(project["project_id"])
    video = repository.create_video(project_id, _video_values())
    video_id = str(video["video_id"])
    repository.update_video(video_id, processing_status="probed")
    repository.execute("DELETE FROM video_workspace_events WHERE project_id=?", (project_id,))
    repository.update_video(video_id, processing_status="annotation_ready")

    delta = repository.workspace_event_changes(project_id, 1)

    assert delta["events"] == []
    assert delta["resync_required"] is True
    assert delta["last_event_id"] > 1


@pytest.fixture
def workspace_api(tmp_path: Path):
    """Build the video API with an isolated event-outbox repository."""

    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    features = VideoFeatureService(repository, storage)
    video_service = VideoService(repository, storage)
    services = {
        get_video_service: video_service,
        get_video_annotation_service: VideoAnnotationService(repository, storage),
        get_video_feature_service: features,
        get_video_model_service: VideoModelService(repository, storage, features),
        get_video_export_service: VideoExportService(repository, storage, features),
        get_video_workspace_sync_service: VideoWorkspaceSyncService(
            repository, video_service
        ),
    }
    app = create_app()
    for dependency, value in services.items():
        app.dependency_overrides[dependency] = lambda value=value: value
    with TestClient(app) as client:
        yield client, repository


def test_snapshot_and_delta_endpoints_return_compact_sync_contract(
    workspace_api,
) -> None:
    """The API exposes one initial snapshot plus typed event deltas."""

    client, repository = workspace_api
    project = client.post("/api/v1/video-projects", json={"name": "API sync"}).json()
    project_id = str(project["project_id"])
    video = repository.create_video(project_id, _video_values())

    snapshot = client.get(
        f"/api/v1/video-projects/{project_id}/workspace-snapshot"
    )
    assert snapshot.status_code == 200
    body = snapshot.json()
    assert set(body) == {
        "project",
        "videos",
        "jobs",
        "processing_options",
        "exports",
        "last_event_id",
    }
    assert body["videos"][0]["video_id"] == video["video_id"]

    delta = client.get(
        f"/api/v1/video-projects/{project_id}/workspace-changes?after=0"
    )
    assert delta.status_code == 200
    event = delta.json()["events"][0]
    assert event["event_type"] == "video.changed"
    assert event["payload"]["video_id"] == video["video_id"]


def test_sse_format_keeps_the_durable_event_envelope() -> None:
    """SSE event names and data preserve the same parser-friendly envelope."""

    payload = {
        "event_id": 7,
        "project_id": "project",
        "video_id": "video",
        "event_type": "job.changed",
        "payload": {"job": {"status": "running"}},
        "created_at": "2026-07-16 00:00:00",
    }

    message = _sse_message("job.changed", payload)

    assert message.startswith("id: 7\nevent: job.changed\n")
    assert json.loads(message.split("data: ", 1)[1]) == payload
