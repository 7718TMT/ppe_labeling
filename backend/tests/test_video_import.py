import io
import sqlite3
from pathlib import Path

import cv2
import numpy as np
import pytest

from backend.app.domain.errors import DuplicateVideoError, VideoValidationError
from backend.app.domain.video import canonical_frame_mapping
from backend.app.repositories.video_db import VIDEO_SCHEMA_VERSION, VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_service import VideoService


def small_video_bytes(tmp_path: Path, fps: float = 12.0, frames: int = 30) -> bytes:
    path = tmp_path / "fixture.mp4"
    writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"), fps, (32, 24))
    assert writer.isOpened()
    for index in range(frames):
        writer.write(np.full((24, 32, 3), (index * 8) % 256, dtype=np.uint8))
    writer.release()
    return path.read_bytes()


def test_video_schema_migration_creates_versioned_relational_tables(tmp_path: Path) -> None:
    database = tmp_path / "state.sqlite3"
    VideoRepository(database)
    with sqlite3.connect(database) as connection:
        version = connection.execute("SELECT max(version) FROM video_schema_migrations").fetchone()[0]
        tables = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        indexes = {row[0] for row in connection.execute("SELECT name FROM sqlite_master WHERE type='index'")}
    assert version == VIDEO_SCHEMA_VERSION
    assert {"video_projects", "videos", "processing_jobs", "video_tracks", "video_segments", "generated_windows", "external_models"} <= tables
    assert "idx_segments_track" in indexes


def test_import_probes_video_and_builds_canonical_mapping(tmp_path: Path) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    service = VideoService(repository, VideoStorageRepository(tmp_path / "storage"))
    project = service.create_project("Factory A")
    imported = service.import_video(project["project_id"], "shift.mp4", io.BytesIO(small_video_bytes(tmp_path)))
    assert imported["original_fps"] == pytest.approx(12, rel=0.1)
    assert imported["canonical_fps"] == 24
    assert imported["canonical_frame_count"] == 60
    mapping = repository.frame_mapping(imported["video_id"])
    assert mapping[0] == {"canonical_frame": 0, "original_frame": 0, "timestamp_seconds": 0.0}
    assert mapping[-1]["original_frame"] == 29
    assert repository.list_jobs(project["project_id"]) == []
    queued = service.queue_pipeline(
        project["project_id"],
        imported["video_id"],
        "threshold",
    )
    assert queued[0]["stage"] == "canonicalize"


def test_duplicate_hash_is_rejected_and_raw_copy_is_cleaned(tmp_path: Path) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    service = VideoService(repository, storage)
    project = service.create_project("Duplicates")
    content = small_video_bytes(tmp_path)
    service.import_video(project["project_id"], "one.mp4", io.BytesIO(content))
    with pytest.raises(DuplicateVideoError):
        service.import_video(project["project_id"], "two.mp4", io.BytesIO(content))
    assert len(list((storage.project_dir(project["project_id"]) / "raw").iterdir())) == 1


def test_import_rejects_a_video_shorter_than_one_analysis_window(tmp_path: Path) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    service = VideoService(repository, storage)
    project = service.create_project("Short video")

    with pytest.raises(
        VideoValidationError,
        match=r'"short\.mp4" is too short.*58 frames.*At least 60 frames',
    ):
        service.import_video(
            project["project_id"], "short.mp4", io.BytesIO(small_video_bytes(tmp_path, frames=29))
        )

    assert repository.list_videos(project["project_id"]) == []
    assert list((storage.project_dir(project["project_id"]) / "raw").iterdir()) == []


def test_canonical_mapping_is_deterministic_for_fractional_fps() -> None:
    first = canonical_frame_mapping(29.97, 300)
    second = canonical_frame_mapping(29.97, 300)
    assert first == second
    assert len(first) == round(300 * 24 / 29.97)
    assert all(current[0] + 1 == following[0] for current, following in zip(first, first[1:], strict=False))
