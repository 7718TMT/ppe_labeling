"""SQLite persistence for pose-video labeling workflow metadata."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Sequence
from uuid import uuid4

from backend.app.domain.errors import (
    RevisionConflictError,
    VideoProcessingConflictError,
    VideoResourceNotFoundError,
)


VIDEO_SCHEMA_VERSION = 2

SCHEMA_V1 = """
CREATE TABLE IF NOT EXISTS video_schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS video_projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    application_version TEXT NOT NULL,
    active_threshold_profile_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS videos (
    video_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES video_projects(project_id) ON DELETE CASCADE,
    filename TEXT NOT NULL,
    relative_path TEXT NOT NULL,
    file_hash TEXT NOT NULL,
    original_fps REAL NOT NULL,
    canonical_fps REAL NOT NULL DEFAULT 24,
    original_frame_count INTEGER NOT NULL,
    canonical_frame_count INTEGER NOT NULL,
    duration_seconds REAL NOT NULL,
    width INTEGER NOT NULL,
    height INTEGER NOT NULL,
    codec TEXT,
    file_size INTEGER NOT NULL,
    folder_group TEXT,
    processing_status TEXT NOT NULL DEFAULT 'imported',
    annotation_status TEXT NOT NULL DEFAULT 'unlabeled',
    quality_status TEXT NOT NULL DEFAULT 'unknown',
    include_in_export INTEGER NOT NULL DEFAULT 1 CHECK (include_in_export IN (0, 1)),
    exclude_reason TEXT,
    annotation_revision INTEGER NOT NULL DEFAULT 0,
    is_approved INTEGER NOT NULL DEFAULT 0 CHECK (is_approved IN (0, 1)),
    approval_revision INTEGER,
    approved_at TEXT,
    pose_cache_version TEXT,
    tracking_cache_version TEXT,
    feature_cache_version TEXT,
    threshold_cache_version TEXT,
    window_cache_version TEXT,
    last_error TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, file_hash)
);
CREATE INDEX IF NOT EXISTS idx_videos_project_status
    ON videos(project_id, processing_status, annotation_status);

CREATE TABLE IF NOT EXISTS canonical_frame_mappings (
    video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    canonical_frame INTEGER NOT NULL,
    original_frame INTEGER NOT NULL,
    timestamp_seconds REAL NOT NULL,
    PRIMARY KEY(video_id, canonical_frame)
);

CREATE TABLE IF NOT EXISTS processing_jobs (
    job_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES video_projects(project_id) ON DELETE CASCADE,
    video_id TEXT REFERENCES videos(video_id) ON DELETE CASCADE,
    stage TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    priority INTEGER NOT NULL DEFAULT 100,
    progress REAL NOT NULL DEFAULT 0 CHECK (progress >= 0 AND progress <= 1),
    error_message TEXT,
    log_json TEXT NOT NULL DEFAULT '[]',
    control_requested TEXT,
    worker_id TEXT,
    retry_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at TEXT,
    heartbeat_at TEXT,
    finished_at TEXT,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_jobs_claim
    ON processing_jobs(status, priority DESC, created_at);
CREATE INDEX IF NOT EXISTS idx_jobs_video ON processing_jobs(video_id, stage, status);

CREATE TABLE IF NOT EXISTS video_tracks (
    track_pk TEXT PRIMARY KEY,
    video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL,
    start_frame INTEGER NOT NULL,
    end_frame INTEGER NOT NULL,
    valid_frame_count INTEGER NOT NULL DEFAULT 0,
    gap_count INTEGER NOT NULL DEFAULT 0,
    avg_person_confidence REAL NOT NULL DEFAULT 0,
    avg_keypoint_confidence REAL NOT NULL DEFAULT 0,
    valid_frame_ratio REAL NOT NULL DEFAULT 0,
    missing_ankle_ratio REAL NOT NULL DEFAULT 1,
    quality_status TEXT NOT NULL DEFAULT 'unknown',
    include_in_export INTEGER NOT NULL DEFAULT 1 CHECK (include_in_export IN (0, 1)),
    exclude_reason TEXT,
    revision INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(video_id, track_id),
    CHECK(start_frame <= end_frame)
);
CREATE INDEX IF NOT EXISTS idx_tracks_video ON video_tracks(video_id, track_id);

CREATE TABLE IF NOT EXISTS video_segments (
    segment_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL,
    start_frame INTEGER NOT NULL,
    end_frame INTEGER NOT NULL,
    label TEXT NOT NULL CHECK(label IN ('others', 'running', 'falling')),
    quality_status TEXT NOT NULL DEFAULT 'good',
    include_in_export INTEGER NOT NULL DEFAULT 1 CHECK (include_in_export IN (0, 1)),
    exclude_reason TEXT,
    annotation_version INTEGER NOT NULL,
    source_type TEXT NOT NULL DEFAULT 'manual',
    source_id TEXT,
    created_by TEXT NOT NULL DEFAULT 'local-user',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CHECK(start_frame <= end_frame)
);
CREATE INDEX IF NOT EXISTS idx_segments_track
    ON video_segments(video_id, track_id, start_frame, end_frame);

CREATE TABLE IF NOT EXISTS annotation_history (
    history_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    operation TEXT NOT NULL,
    old_value_json TEXT,
    new_value_json TEXT,
    revision INTEGER NOT NULL,
    user_id TEXT NOT NULL DEFAULT 'local-user',
    undone INTEGER NOT NULL DEFAULT 0 CHECK (undone IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_history_video ON annotation_history(video_id, revision DESC);

CREATE TABLE IF NOT EXISTS generated_windows (
    window_id TEXT PRIMARY KEY,
    video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL,
    start_frame INTEGER NOT NULL,
    end_frame INTEGER NOT NULL,
    label TEXT CHECK(label IN ('others', 'running', 'falling')),
    label_reason TEXT,
    quality_score REAL NOT NULL DEFAULT 0,
    quality_status TEXT NOT NULL DEFAULT 'unlabeled',
    include_in_export INTEGER NOT NULL DEFAULT 0 CHECK (include_in_export IN (0, 1)),
    exclude_reason TEXT,
    window_config_version TEXT NOT NULL,
    feature_status TEXT NOT NULL DEFAULT 'pending',
    stale INTEGER NOT NULL DEFAULT 0 CHECK (stale IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(video_id, track_id, start_frame, window_config_version)
);
CREATE INDEX IF NOT EXISTS idx_windows_video_track
    ON generated_windows(video_id, track_id, start_frame);

CREATE TABLE IF NOT EXISTS threshold_profiles (
    threshold_profile_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES video_projects(project_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    config_json TEXT NOT NULL,
    is_default INTEGER NOT NULL DEFAULT 0 CHECK (is_default IN (0, 1)),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, name, version)
);

CREATE TABLE IF NOT EXISTS threshold_suggestions (
    suggestion_id TEXT PRIMARY KEY,
    threshold_profile_id TEXT NOT NULL REFERENCES threshold_profiles(threshold_profile_id),
    video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL,
    start_frame INTEGER NOT NULL,
    end_frame INTEGER NOT NULL,
    suggested_label TEXT NOT NULL CHECK(suggested_label IN ('running', 'falling')),
    confidence REAL NOT NULL,
    triggered_conditions_json TEXT NOT NULL,
    supporting_features_json TEXT NOT NULL,
    quality_status TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK(review_status IN ('pending', 'accepted', 'modified', 'rejected')),
    artifact_key TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(threshold_profile_id, video_id, track_id, artifact_key)
);
CREATE INDEX IF NOT EXISTS idx_threshold_suggestions_video
    ON threshold_suggestions(video_id, track_id, review_status);

CREATE TABLE IF NOT EXISTS external_models (
    external_model_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES video_projects(project_id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    version TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    artifact_hash TEXT NOT NULL,
    adapter_type TEXT NOT NULL,
    class_map_json TEXT NOT NULL,
    feature_schema_version TEXT NOT NULL,
    feature_columns_json TEXT NOT NULL,
    window_config_json TEXT NOT NULL,
    compatibility_status TEXT NOT NULL,
    compatibility_errors_json TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL,
    is_active INTEGER NOT NULL DEFAULT 0 CHECK (is_active IN (0, 1)),
    loaded_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(project_id, name, version, artifact_hash)
);

CREATE TABLE IF NOT EXISTS model_window_predictions (
    prediction_id TEXT PRIMARY KEY,
    external_model_id TEXT NOT NULL REFERENCES external_models(external_model_id) ON DELETE CASCADE,
    window_id TEXT NOT NULL REFERENCES generated_windows(window_id) ON DELETE CASCADE,
    others_probability REAL NOT NULL,
    running_probability REAL NOT NULL,
    falling_probability REAL NOT NULL,
    predicted_label TEXT NOT NULL CHECK(predicted_label IN ('others', 'running', 'falling')),
    confidence REAL NOT NULL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(external_model_id, window_id)
);

CREATE TABLE IF NOT EXISTS model_suggestions (
    suggestion_id TEXT PRIMARY KEY,
    external_model_id TEXT NOT NULL REFERENCES external_models(external_model_id) ON DELETE CASCADE,
    video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    track_id INTEGER NOT NULL,
    start_frame INTEGER NOT NULL,
    end_frame INTEGER NOT NULL,
    suggested_label TEXT NOT NULL CHECK(suggested_label IN ('running', 'falling')),
    confidence REAL NOT NULL,
    source_window_ids_json TEXT NOT NULL,
    probabilities_json TEXT NOT NULL,
    merge_config_json TEXT NOT NULL,
    review_status TEXT NOT NULL DEFAULT 'pending'
        CHECK(review_status IN ('pending', 'accepted', 'modified', 'rejected')),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_model_suggestions_video
    ON model_suggestions(video_id, track_id, review_status);

CREATE TABLE IF NOT EXISTS video_exports (
    export_id TEXT PRIMARY KEY,
    project_id TEXT NOT NULL REFERENCES video_projects(project_id) ON DELETE CASCADE,
    job_id TEXT REFERENCES processing_jobs(job_id) ON DELETE SET NULL,
    status TEXT NOT NULL DEFAULT 'queued',
    artifact_path TEXT,
    manifest_json TEXT,
    validation_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS video_workspace_state (
    project_id TEXT PRIMARY KEY REFERENCES video_projects(project_id) ON DELETE CASCADE,
    video_id TEXT,
    track_id INTEGER,
    frame_index INTEGER NOT NULL DEFAULT 0,
    suggestion_source TEXT NOT NULL DEFAULT 'Threshold',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
"""


JSON_COLUMNS = {
    "config_json",
    "log_json",
    "old_value_json",
    "new_value_json",
    "triggered_conditions_json",
    "supporting_features_json",
    "class_map_json",
    "feature_columns_json",
    "window_config_json",
    "compatibility_errors_json",
    "metadata_json",
    "source_window_ids_json",
    "probabilities_json",
    "merge_config_json",
    "manifest_json",
    "validation_json",
}


class VideoRepository:
    """Own all structured pose-video persistence and migration boundaries."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        self._migrate()

    @contextmanager
    def connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
        finally:
            connection.close()

    def _migrate(self) -> None:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self.connection() as connection, connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.executescript(SCHEMA_V1)
            applied = {
                int(row[0])
                for row in connection.execute(
                    "SELECT version FROM video_schema_migrations"
                )
            }
            if 1 not in applied:
                connection.execute(
                    "INSERT INTO video_schema_migrations(version) VALUES (1)"
                )
            if 2 not in applied:
                self._migrate_v2(connection)
                connection.execute(
                    "INSERT INTO video_schema_migrations(version) VALUES (2)"
                )

    @staticmethod
    def _migrate_v2(connection: sqlite3.Connection) -> None:
        """Persist a processing target and enforce one active job per video."""

        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(processing_jobs)")
        }
        if "target_mode" not in columns:
            connection.execute(
                """
                ALTER TABLE processing_jobs
                ADD COLUMN target_mode TEXT NOT NULL DEFAULT 'threshold'
                    CHECK(target_mode IN ('threshold', 'model'))
                """
            )
        if "external_model_id" not in columns:
            connection.execute(
                """
                ALTER TABLE processing_jobs
                ADD COLUMN external_model_id TEXT
                    REFERENCES external_models(external_model_id)
                """
            )

        connection.execute(
            """
            UPDATE processing_jobs
            SET target_mode='model',
                external_model_id=CASE
                    WHEN EXISTS (
                        SELECT 1 FROM external_models
                        WHERE external_model_id=substr(processing_jobs.stage, 7)
                    )
                    THEN substr(stage, 7)
                    ELSE NULL
                END,
                stage='model'
            WHERE stage LIKE 'model:%'
            """
        )

        active_jobs = connection.execute(
            """
            SELECT job_id, video_id
            FROM processing_jobs
            WHERE video_id IS NOT NULL
              AND status IN ('queued', 'running', 'paused')
            ORDER BY video_id,
                     CASE status
                         WHEN 'running' THEN 0
                         WHEN 'paused' THEN 1
                         ELSE 2
                     END,
                     priority DESC,
                     created_at,
                     job_id
            """
        ).fetchall()
        retained_videos: set[str] = set()
        for row in active_jobs:
            video_id = str(row["video_id"])
            if video_id not in retained_videos:
                retained_videos.add(video_id)
                continue
            connection.execute(
                """
                UPDATE processing_jobs
                SET status='cancelled',
                    error_message='Superseded by the active video pipeline during migration',
                    control_requested=NULL,
                    finished_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP
                WHERE job_id=?
                """,
                (row["job_id"],),
            )

        active_models = connection.execute(
            """
            SELECT external_model_id, project_id
            FROM external_models
            WHERE is_active=1
            ORDER BY project_id, loaded_at DESC, external_model_id
            """
        ).fetchall()
        retained_projects: set[str] = set()
        for row in active_models:
            project_id = str(row["project_id"])
            if project_id not in retained_projects:
                retained_projects.add(project_id)
                continue
            connection.execute(
                "UPDATE external_models SET is_active=0 WHERE external_model_id=?",
                (row["external_model_id"],),
            )

        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_processing_jobs_active_video
            ON processing_jobs(video_id)
            WHERE video_id IS NOT NULL
              AND status IN ('queued', 'running', 'paused')
            """
        )
        connection.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS uq_external_models_active_project
            ON external_models(project_id)
            WHERE is_active=1
            """
        )

    @staticmethod
    def _decode(row: sqlite3.Row | None) -> dict[str, Any] | None:
        if row is None:
            return None
        result = dict(row)
        for key in JSON_COLUMNS.intersection(result):
            if result[key] is not None:
                result[key.removesuffix("_json")] = json.loads(result[key])
        return result

    def one(self, sql: str, values: Sequence[Any] = ()) -> dict[str, Any] | None:
        with self.connection() as connection:
            return self._decode(connection.execute(sql, values).fetchone())

    def all(self, sql: str, values: Sequence[Any] = ()) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return [self._decode(row) or {} for row in connection.execute(sql, values).fetchall()]

    def execute(self, sql: str, values: Sequence[Any] = ()) -> None:
        with self.connection() as connection, connection:
            connection.execute(sql, values)

    def create_project(self, name: str, config: dict[str, Any], application_version: str) -> dict[str, Any]:
        project_id = uuid4().hex
        with self.connection() as connection, connection:
            connection.execute(
                "INSERT INTO video_projects(project_id,name,config_json,application_version) VALUES (?,?,?,?)",
                (project_id, name, json.dumps(config, sort_keys=True), application_version),
            )
        return self.get_project(project_id)

    def get_project(self, project_id: str) -> dict[str, Any]:
        project = self.one("SELECT * FROM video_projects WHERE project_id = ?", (project_id,))
        if project is None:
            raise VideoResourceNotFoundError("Video project not found")
        return project

    def list_projects(self) -> list[dict[str, Any]]:
        return self.all("SELECT * FROM video_projects ORDER BY updated_at DESC")

    def update_project(self, project_id: str, config: dict[str, Any]) -> dict[str, Any]:
        self.get_project(project_id)
        self.execute(
            "UPDATE video_projects SET config_json=?, updated_at=CURRENT_TIMESTAMP WHERE project_id=?",
            (json.dumps(config, sort_keys=True), project_id),
        )
        return self.get_project(project_id)

    def create_video(self, project_id: str, values: dict[str, Any], video_id: str | None = None) -> dict[str, Any]:
        video_id = video_id or uuid4().hex
        fields = ["video_id", "project_id", *values.keys()]
        placeholders = ",".join("?" for _ in fields)
        with self.connection() as connection, connection:
            connection.execute(
                f"INSERT INTO videos({','.join(fields)}) VALUES ({placeholders})",
                [video_id, project_id, *values.values()],
            )
        return self.get_video(video_id)

    def get_video(self, video_id: str) -> dict[str, Any]:
        video = self.one("SELECT * FROM videos WHERE video_id=?", (video_id,))
        if video is None:
            raise VideoResourceNotFoundError("Video not found")
        return video

    def list_videos(self, project_id: str, status: str | None = None) -> list[dict[str, Any]]:
        self.get_project(project_id)
        if status:
            return self.all(
                "SELECT * FROM videos WHERE project_id=? AND (processing_status=? OR annotation_status=? OR quality_status=?) ORDER BY created_at",
                (project_id, status, status, status),
            )
        return self.all("SELECT * FROM videos WHERE project_id=? ORDER BY created_at", (project_id,))

    def update_video(self, video_id: str, **values: Any) -> dict[str, Any]:
        if not values:
            return self.get_video(video_id)
        self.get_video(video_id)
        assignments = ",".join(f"{key}=?" for key in values)
        self.execute(
            f"UPDATE videos SET {assignments}, updated_at=CURRENT_TIMESTAMP WHERE video_id=?",
            [*values.values(), video_id],
        )
        return self.get_video(video_id)

    def delete_video(self, project_id: str, video_id: str) -> dict[str, Any]:
        """Delete one project video and all rows that depend on it.

        The ownership check, workspace reset, and parent-row deletion share one
        transaction. SQLite foreign-key cascades remove frame mappings, jobs,
        tracks, annotations and history, windows, predictions, and suggestions.
        Project-scoped profiles, external model packages, and exports are not
        video-owned and deliberately remain intact.
        """

        with self.connection() as connection, connection:
            row = connection.execute(
                "SELECT * FROM videos WHERE project_id=? AND video_id=?",
                (project_id, video_id),
            ).fetchone()
            if row is None:
                raise VideoResourceNotFoundError("Video not found in project")
            connection.execute(
                """
                UPDATE video_workspace_state
                SET video_id=NULL,
                    track_id=NULL,
                    frame_index=0,
                    updated_at=CURRENT_TIMESTAMP
                WHERE project_id=? AND video_id=?
                """,
                (project_id, video_id),
            )
            connection.execute(
                "DELETE FROM videos WHERE project_id=? AND video_id=?",
                (project_id, video_id),
            )
        return self._decode(row) or {}

    def replace_frame_mapping(self, video_id: str, mapping: Sequence[tuple[int, int, float]]) -> None:
        with self.connection() as connection, connection:
            connection.execute("DELETE FROM canonical_frame_mappings WHERE video_id=?", (video_id,))
            connection.executemany(
                "INSERT INTO canonical_frame_mappings(video_id,canonical_frame,original_frame,timestamp_seconds) VALUES (?,?,?,?)",
                [(video_id, *row) for row in mapping],
            )

    def frame_mapping(self, video_id: str) -> list[dict[str, Any]]:
        return self.all(
            "SELECT canonical_frame,original_frame,timestamp_seconds FROM canonical_frame_mappings WHERE video_id=? ORDER BY canonical_frame",
            (video_id,),
        )

    def enqueue_job(
        self,
        project_id: str,
        stage: str,
        video_id: str | None = None,
        priority: int = 100,
        *,
        target_mode: str = "threshold",
        external_model_id: str | None = None,
    ) -> dict[str, Any]:
        if video_id is not None:
            return self.enqueue_pipeline_job(
                project_id,
                video_id,
                stage,
                target_mode,
                external_model_id,
                priority,
            )
        existing = self.one(
            "SELECT * FROM processing_jobs WHERE project_id=? AND video_id IS ? AND stage=? AND status IN ('queued','running','paused') ORDER BY created_at DESC LIMIT 1",
            (project_id, video_id, stage),
        )
        if existing:
            return existing
        job_id = uuid4().hex
        self.execute(
            "INSERT INTO processing_jobs(job_id,project_id,video_id,stage,priority) VALUES (?,?,?,?,?)",
            (job_id, project_id, video_id, stage, priority),
        )
        return self.get_job(job_id)

    def enqueue_pipeline_job(
        self,
        project_id: str,
        video_id: str,
        stage: str,
        target_mode: str,
        external_model_id: str | None,
        priority: int = 100,
    ) -> dict[str, Any]:
        """Create one persistent video pipeline or reuse its identical intent."""

        if target_mode not in {"threshold", "model"}:
            raise ValueError("Pipeline target must be threshold or model")
        if target_mode == "model" and not external_model_id:
            raise ValueError("Model pipelines require an external model ID")
        if target_mode == "threshold":
            external_model_id = None

        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            video = connection.execute(
                "SELECT project_id FROM videos WHERE video_id=?",
                (video_id,),
            ).fetchone()
            if video is None or str(video["project_id"]) != project_id:
                raise VideoResourceNotFoundError("Video not found in project")

            active = connection.execute(
                """
                SELECT * FROM processing_jobs
                WHERE video_id=?
                  AND status IN ('queued', 'running', 'paused')
                ORDER BY created_at DESC
                LIMIT 1
                """,
                (video_id,),
            ).fetchone()
            if active is not None:
                decoded = self._decode(active) or {}
                same_model = (
                    decoded.get("external_model_id") == external_model_id
                )
                if decoded.get("target_mode") == target_mode and same_model:
                    connection.commit()
                    return decoded
                active_label = str(decoded.get("target_mode", "threshold")).title()
                raise VideoProcessingConflictError(
                    f"This video is already processing with {active_label} suggestions"
                )

            job_id = uuid4().hex
            connection.execute(
                """
                INSERT INTO processing_jobs(
                    job_id, project_id, video_id, stage, priority,
                    target_mode, external_model_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    project_id,
                    video_id,
                    stage,
                    priority,
                    target_mode,
                    external_model_id,
                ),
            )
            row = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            connection.commit()
        return self._decode(row) or {}

    def active_job_for_video(self, video_id: str) -> dict[str, Any] | None:
        """Return the single queued, running, or paused pipeline for a video."""

        return self.one(
            """
            SELECT * FROM processing_jobs
            WHERE video_id=? AND status IN ('queued', 'running', 'paused')
            ORDER BY created_at DESC LIMIT 1
            """,
            (video_id,),
        )

    def get_job(self, job_id: str) -> dict[str, Any]:
        job = self.one("SELECT * FROM processing_jobs WHERE job_id=?", (job_id,))
        if job is None:
            raise VideoResourceNotFoundError("Processing job not found")
        return job

    def list_jobs(self, project_id: str) -> list[dict[str, Any]]:
        return self.all(
            "SELECT * FROM processing_jobs WHERE project_id=? ORDER BY CASE status WHEN 'running' THEN 0 WHEN 'queued' THEN 1 WHEN 'paused' THEN 2 ELSE 3 END, priority DESC, created_at",
            (project_id,),
        )

    def claim_job(self, worker_id: str) -> dict[str, Any] | None:
        with self.connection() as connection, connection:
            row = connection.execute(
                "SELECT * FROM processing_jobs WHERE status='queued' ORDER BY priority DESC, created_at LIMIT 1"
            ).fetchone()
            if row is None:
                return None
            updated = connection.execute(
                "UPDATE processing_jobs SET status='running',worker_id=?,started_at=COALESCE(started_at,CURRENT_TIMESTAMP),heartbeat_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=? AND status='queued'",
                (worker_id, row["job_id"]),
            )
            if updated.rowcount != 1:
                return None
            return self._decode(connection.execute("SELECT * FROM processing_jobs WHERE job_id=?", (row["job_id"],)).fetchone())

    def update_job(self, job_id: str, **values: Any) -> dict[str, Any]:
        if "log" in values:
            values["log_json"] = json.dumps(values.pop("log"))
        assignments = ",".join(f"{key}=?" for key in values)
        if assignments:
            self.execute(
                f"UPDATE processing_jobs SET {assignments},heartbeat_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=?",
                [*values.values(), job_id],
            )
        return self.get_job(job_id)

    def complete_job_and_enqueue_next(
        self,
        job_id: str,
        next_stage: str | None,
    ) -> tuple[dict[str, Any], dict[str, Any] | None]:
        """Complete a stage and persist its successor in one transaction."""

        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise VideoResourceNotFoundError("Processing job not found")
            if row["status"] != "running":
                connection.commit()
                return self._decode(row) or {}, None

            connection.execute(
                """
                UPDATE processing_jobs
                SET status='completed',
                    progress=1.0,
                    control_requested=NULL,
                    finished_at=CURRENT_TIMESTAMP,
                    heartbeat_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP
                WHERE job_id=?
                """,
                (job_id,),
            )
            next_row: sqlite3.Row | None = None
            if next_stage is not None:
                next_id = uuid4().hex
                connection.execute(
                    """
                    INSERT INTO processing_jobs(
                        job_id, project_id, video_id, stage, priority,
                        target_mode, external_model_id
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        next_id,
                        row["project_id"],
                        row["video_id"],
                        next_stage,
                        max(0, int(row["priority"]) - 1),
                        row["target_mode"],
                        row["external_model_id"],
                    ),
                )
                next_row = connection.execute(
                    "SELECT * FROM processing_jobs WHERE job_id=?",
                    (next_id,),
                ).fetchone()
            completed = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            connection.commit()
        return self._decode(completed) or {}, self._decode(next_row)

    def retry_job(self, job_id: str) -> dict[str, Any]:
        """Requeue a failed stage without violating the active-video invariant."""

        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            row = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            if row is None:
                raise VideoResourceNotFoundError("Processing job not found")
            if row["status"] not in {"failed", "cancelled"}:
                raise VideoProcessingConflictError(
                    "Only failed or cancelled jobs can be retried"
                )
            if row["video_id"] is not None:
                active = connection.execute(
                    """
                    SELECT target_mode FROM processing_jobs
                    WHERE video_id=?
                      AND status IN ('queued', 'running', 'paused')
                    LIMIT 1
                    """,
                    (row["video_id"],),
                ).fetchone()
                if active is not None:
                    raise VideoProcessingConflictError(
                        "This video already has an active processing job"
                    )
            connection.execute(
                """
                UPDATE processing_jobs
                SET status='queued',
                    progress=0,
                    error_message=NULL,
                    control_requested=NULL,
                    retry_count=retry_count+1,
                    worker_id=NULL,
                    started_at=NULL,
                    heartbeat_at=NULL,
                    finished_at=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE job_id=?
                """,
                (job_id,),
            )
            retried = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            connection.commit()
        return self._decode(retried) or {}

    def recover_stale_jobs(self, stale_seconds: int = 60) -> int:
        with self.connection() as connection, connection:
            cursor = connection.execute(
                "UPDATE processing_jobs SET status='queued',worker_id=NULL,control_requested=NULL,error_message='Recovered after stale worker heartbeat',updated_at=CURRENT_TIMESTAMP WHERE status='running' AND (heartbeat_at IS NULL OR heartbeat_at <= datetime('now', ?))",
                (f"-{max(1, stale_seconds)} seconds",),
            )
            return cursor.rowcount

    def replace_tracks(
        self,
        video_id: str,
        tracks: Sequence[dict[str, Any]],
        *,
        invalidate_derived: bool = False,
    ) -> None:
        """Replace track summaries while optionally invalidating dependants."""

        with self.connection() as connection, connection:
            connection.execute("DELETE FROM video_tracks WHERE video_id=?", (video_id,))
            for track in tracks:
                fields = ["track_pk", "video_id", *track.keys()]
                connection.execute(
                    f"INSERT INTO video_tracks({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                    [uuid4().hex, video_id, *track.values()],
                )
            if invalidate_derived:
                connection.execute(
                    "DELETE FROM threshold_suggestions WHERE video_id=?",
                    (video_id,),
                )
                connection.execute(
                    "DELETE FROM model_suggestions WHERE video_id=?",
                    (video_id,),
                )
                connection.execute(
                    "DELETE FROM generated_windows WHERE video_id=?",
                    (video_id,),
                )
                connection.execute(
                    """
                    UPDATE videos
                    SET feature_cache_version=NULL,
                        threshold_cache_version=NULL,
                        window_cache_version=NULL,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE video_id=?
                    """,
                    (video_id,),
                )

    def list_tracks(self, video_id: str, include_excluded: bool = True) -> list[dict[str, Any]]:
        self.get_video(video_id)
        clause = "" if include_excluded else " AND include_in_export=1"
        return self.all(f"SELECT * FROM video_tracks WHERE video_id=?{clause} ORDER BY track_id", (video_id,))

    def get_track(self, video_id: str, track_id: int) -> dict[str, Any]:
        track = self.one("SELECT * FROM video_tracks WHERE video_id=? AND track_id=?", (video_id, track_id))
        if track is None:
            raise VideoResourceNotFoundError("Track not found")
        return track

    def update_track(self, video_id: str, track_id: int, **values: Any) -> dict[str, Any]:
        self.get_track(video_id, track_id)
        assignments = ",".join(f"{key}=?" for key in values)
        self.execute(
            f"UPDATE video_tracks SET {assignments},revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE video_id=? AND track_id=?",
            [*values.values(), video_id, track_id],
        )
        return self.get_track(video_id, track_id)

    def list_segments(self, video_id: str, track_id: int | None = None) -> list[dict[str, Any]]:
        self.get_video(video_id)
        if track_id is None:
            return self.all("SELECT * FROM video_segments WHERE video_id=? ORDER BY track_id,start_frame", (video_id,))
        return self.all(
            "SELECT * FROM video_segments WHERE video_id=? AND track_id=? ORDER BY start_frame",
            (video_id, track_id),
        )

    def write_segment(
        self,
        video_id: str,
        payload: dict[str, Any],
        expected_revision: int,
        segment_id: str | None = None,
    ) -> tuple[dict[str, Any], int]:
        with self.connection() as connection, connection:
            video = connection.execute("SELECT annotation_revision FROM videos WHERE video_id=?", (video_id,)).fetchone()
            if video is None:
                raise VideoResourceNotFoundError("Video not found")
            if video["annotation_revision"] != expected_revision:
                raise RevisionConflictError(
                    f"Annotation revision conflict: expected {expected_revision}, current {video['annotation_revision']}"
                )
            old: dict[str, Any] | None = None
            operation = "create"
            if segment_id:
                existing = connection.execute("SELECT * FROM video_segments WHERE segment_id=? AND video_id=?", (segment_id, video_id)).fetchone()
                if existing is None:
                    raise VideoResourceNotFoundError("Segment not found")
                old = dict(existing)
                operation = "update"
            else:
                segment_id = uuid4().hex
            revision = expected_revision + 1
            fields = {**payload, "annotation_version": revision}
            if operation == "create":
                names = ["segment_id", "video_id", *fields.keys()]
                connection.execute(
                    f"INSERT INTO video_segments({','.join(names)}) VALUES ({','.join('?' for _ in names)})",
                    [segment_id, video_id, *fields.values()],
                )
            else:
                connection.execute(
                    f"UPDATE video_segments SET {','.join(f'{key}=?' for key in fields)},updated_at=CURRENT_TIMESTAMP WHERE segment_id=?",
                    [*fields.values(), segment_id],
                )
            new = dict(connection.execute("SELECT * FROM video_segments WHERE segment_id=?", (segment_id,)).fetchone())
            self._record_history(connection, video_id, segment_id, operation, old, new, revision)
            self._bump_annotation_revision(connection, video_id, revision)
        return new, revision

    def delete_segment(self, video_id: str, segment_id: str, expected_revision: int) -> int:
        with self.connection() as connection, connection:
            video = connection.execute("SELECT annotation_revision FROM videos WHERE video_id=?", (video_id,)).fetchone()
            if video is None:
                raise VideoResourceNotFoundError("Video not found")
            if video[0] != expected_revision:
                raise RevisionConflictError(f"Annotation revision conflict: expected {expected_revision}, current {video[0]}")
            old_row = connection.execute("SELECT * FROM video_segments WHERE segment_id=? AND video_id=?", (segment_id, video_id)).fetchone()
            if old_row is None:
                raise VideoResourceNotFoundError("Segment not found")
            revision = expected_revision + 1
            connection.execute("DELETE FROM video_segments WHERE segment_id=?", (segment_id,))
            self._record_history(connection, video_id, segment_id, "delete", dict(old_row), None, revision)
            self._bump_annotation_revision(connection, video_id, revision)
        return revision

    @staticmethod
    def _record_history(
        connection: sqlite3.Connection,
        video_id: str,
        entity_id: str,
        operation: str,
        old: dict[str, Any] | None,
        new: dict[str, Any] | None,
        revision: int,
    ) -> None:
        connection.execute(
            "INSERT INTO annotation_history(history_id,video_id,entity_type,entity_id,operation,old_value_json,new_value_json,revision) VALUES (?,?,?,?,?,?,?,?)",
            (uuid4().hex, video_id, "segment", entity_id, operation, json.dumps(old), json.dumps(new), revision),
        )

    @staticmethod
    def _bump_annotation_revision(connection: sqlite3.Connection, video_id: str, revision: int) -> None:
        connection.execute(
            "UPDATE videos SET annotation_revision=?,is_approved=0,approval_revision=NULL,approved_at=NULL,annotation_status='labeled',window_cache_version=NULL,updated_at=CURRENT_TIMESTAMP WHERE video_id=?",
            (revision, video_id),
        )
        connection.execute("UPDATE generated_windows SET stale=1 WHERE video_id=?", (video_id,))

    def list_history(self, video_id: str) -> list[dict[str, Any]]:
        return self.all("SELECT * FROM annotation_history WHERE video_id=? ORDER BY revision DESC", (video_id,))

    def undo_or_redo(self, video_id: str, expected_revision: int, mode: str) -> int:
        """Apply one history transition while retaining a complete audit trail."""

        if mode not in {"undo", "redo"}:
            raise ValueError("History mode must be undo or redo")
        with self.connection() as connection, connection:
            video = connection.execute("SELECT annotation_revision FROM videos WHERE video_id=?", (video_id,)).fetchone()
            if video is None:
                raise VideoResourceNotFoundError("Video not found")
            if video[0] != expected_revision:
                raise RevisionConflictError(f"Annotation revision conflict: expected {expected_revision}, current {video[0]}")
            if mode == "undo":
                history = connection.execute(
                    "SELECT * FROM annotation_history WHERE video_id=? AND operation IN ('create','update','delete') AND undone=0 ORDER BY revision DESC LIMIT 1",
                    (video_id,),
                ).fetchone()
                if history is None:
                    raise VideoResourceNotFoundError("Nothing to undo")
                desired = json.loads(history["old_value_json"]) if history["old_value_json"] else None
                source_history_id = history["history_id"]
            else:
                history = connection.execute(
                    "SELECT * FROM annotation_history WHERE video_id=? AND operation='undo' AND undone=0 ORDER BY revision DESC LIMIT 1",
                    (video_id,),
                ).fetchone()
                if history is None:
                    raise VideoResourceNotFoundError("Nothing to redo")
                desired = json.loads(history["old_value_json"]) if history["old_value_json"] else None
                source_history_id = history["history_id"]
            current_row = connection.execute("SELECT * FROM video_segments WHERE segment_id=?", (history["entity_id"],)).fetchone()
            current = dict(current_row) if current_row else None
            if desired is None:
                connection.execute("DELETE FROM video_segments WHERE segment_id=?", (history["entity_id"],))
            else:
                columns = [
                    "segment_id", "video_id", "track_id", "start_frame", "end_frame", "label",
                    "quality_status", "include_in_export", "exclude_reason",
                    "annotation_version", "source_type", "source_id", "created_by", "created_at", "updated_at",
                ]
                connection.execute(
                    f"INSERT OR REPLACE INTO video_segments({','.join(columns)}) VALUES ({','.join('?' for _ in columns)})",
                    [desired.get(column) for column in columns],
                )
            revision = expected_revision + 1
            connection.execute("UPDATE annotation_history SET undone=1 WHERE history_id=?", (source_history_id,))
            if mode == "redo" and str(history["user_id"]).startswith("undo:"):
                connection.execute("UPDATE annotation_history SET undone=0 WHERE history_id=?", (str(history["user_id"]).split(":", 1)[1],))
            connection.execute(
                "INSERT INTO annotation_history(history_id,video_id,entity_type,entity_id,operation,old_value_json,new_value_json,revision,user_id) VALUES (?,?,?,?,?,?,?,?,?)",
                (uuid4().hex, video_id, "segment", history["entity_id"], mode, json.dumps(current), json.dumps(desired), revision, f"{mode}:{source_history_id}"),
            )
            self._bump_annotation_revision(connection, video_id, revision)
        return revision

    def replace_windows(self, video_id: str, windows: Sequence[dict[str, Any]]) -> None:
        with self.connection() as connection, connection:
            connection.execute("DELETE FROM generated_windows WHERE video_id=?", (video_id,))
            for window in windows:
                fields = ["window_id", "video_id", *window.keys()]
                connection.execute(
                    f"INSERT INTO generated_windows({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                    [uuid4().hex, video_id, *window.values()],
                )

    def list_windows(self, video_id: str, track_id: int | None = None) -> list[dict[str, Any]]:
        if track_id is None:
            return self.all("SELECT * FROM generated_windows WHERE video_id=? ORDER BY track_id,start_frame", (video_id,))
        return self.all(
            "SELECT * FROM generated_windows WHERE video_id=? AND track_id=? ORDER BY start_frame",
            (video_id, track_id),
        )

    def create_threshold_profile(
        self, project_id: str, name: str, version: str, config: dict[str, Any], is_default: bool = False
    ) -> dict[str, Any]:
        profile_id = uuid4().hex
        with self.connection() as connection, connection:
            connection.execute(
                "INSERT INTO threshold_profiles(threshold_profile_id,project_id,name,version,config_json,is_default) VALUES (?,?,?,?,?,?)",
                (profile_id, project_id, name, version, json.dumps(config, sort_keys=True), int(is_default)),
            )
            if is_default:
                connection.execute(
                    "UPDATE video_projects SET active_threshold_profile_id=?,updated_at=CURRENT_TIMESTAMP WHERE project_id=?",
                    (profile_id, project_id),
                )
        return self.get_threshold_profile(profile_id)

    def get_threshold_profile(self, profile_id: str) -> dict[str, Any]:
        profile = self.one("SELECT * FROM threshold_profiles WHERE threshold_profile_id=?", (profile_id,))
        if profile is None:
            raise VideoResourceNotFoundError("Threshold profile not found")
        return profile

    def list_threshold_profiles(self, project_id: str) -> list[dict[str, Any]]:
        return self.all("SELECT * FROM threshold_profiles WHERE project_id=? ORDER BY updated_at DESC", (project_id,))

    def replace_threshold_suggestions(
        self, video_id: str, profile_id: str, suggestions: Sequence[dict[str, Any]]
    ) -> None:
        with self.connection() as connection, connection:
            connection.execute(
                "DELETE FROM threshold_suggestions WHERE video_id=? AND threshold_profile_id=? AND review_status='pending'",
                (video_id, profile_id),
            )
            for suggestion in suggestions:
                fields = ["suggestion_id", "threshold_profile_id", "video_id", *suggestion.keys()]
                values = [uuid4().hex, profile_id, video_id, *suggestion.values()]
                connection.execute(
                    f"INSERT OR IGNORE INTO threshold_suggestions({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                    values,
                )

    def list_suggestions(self, table: str, video_id: str, track_id: int | None = None) -> list[dict[str, Any]]:
        if table not in {"threshold_suggestions", "model_suggestions"}:
            raise ValueError("Unsupported suggestion table")
        values: list[Any] = [video_id]
        clause = "video_id=?"
        if track_id is not None:
            clause += " AND track_id=?"
            values.append(track_id)
        return self.all(f"SELECT * FROM {table} WHERE {clause} ORDER BY start_frame", values)

    def review_suggestion(self, table: str, suggestion_id: str, status: str) -> dict[str, Any]:
        if table not in {"threshold_suggestions", "model_suggestions"}:
            raise ValueError("Unsupported suggestion table")
        self.execute(
            f"UPDATE {table} SET review_status=?,updated_at=CURRENT_TIMESTAMP WHERE suggestion_id=?",
            (status, suggestion_id),
        )
        suggestion = self.one(f"SELECT * FROM {table} WHERE suggestion_id=?", (suggestion_id,))
        if suggestion is None:
            raise VideoResourceNotFoundError("Suggestion not found")
        return suggestion

    def save_workspace_state(self, project_id: str, state: dict[str, Any]) -> None:
        self.execute(
            "INSERT INTO video_workspace_state(project_id,video_id,track_id,frame_index,suggestion_source) VALUES (?,?,?,?,?) ON CONFLICT(project_id) DO UPDATE SET video_id=excluded.video_id,track_id=excluded.track_id,frame_index=excluded.frame_index,suggestion_source=excluded.suggestion_source,updated_at=CURRENT_TIMESTAMP",
            (project_id, state.get("video_id"), state.get("track_id"), state.get("frame_index", 0), state.get("suggestion_source", "Threshold")),
        )

    def workspace_state(self, project_id: str) -> dict[str, Any] | None:
        return self.one("SELECT * FROM video_workspace_state WHERE project_id=?", (project_id,))

    def create_external_model(self, project_id: str, model_id: str, values: dict[str, Any]) -> dict[str, Any]:
        fields = ["external_model_id", "project_id", *values.keys()]
        self.execute(
            f"INSERT INTO external_models({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
            [model_id, project_id, *values.values()],
        )
        return self.get_external_model(model_id)

    def get_external_model(self, model_id: str) -> dict[str, Any]:
        model = self.one("SELECT * FROM external_models WHERE external_model_id=?", (model_id,))
        if model is None:
            raise VideoResourceNotFoundError("External model not found")
        return model

    def list_external_models(self, project_id: str) -> list[dict[str, Any]]:
        return self.all("SELECT * FROM external_models WHERE project_id=? ORDER BY loaded_at DESC", (project_id,))

    def active_external_model(self, project_id: str) -> dict[str, Any] | None:
        """Return the project model selected for inference suggestions."""

        return self.one(
            """
            SELECT * FROM external_models
            WHERE project_id=? AND is_active=1
            ORDER BY loaded_at DESC
            LIMIT 1
            """,
            (project_id,),
        )

    def activate_external_model(self, project_id: str, model_id: str) -> dict[str, Any]:
        model = self.get_external_model(model_id)
        if model["project_id"] != project_id:
            raise VideoResourceNotFoundError("External model not found in project")
        with self.connection() as connection, connection:
            connection.execute("UPDATE external_models SET is_active=0 WHERE project_id=?", (project_id,))
            connection.execute("UPDATE external_models SET is_active=1 WHERE external_model_id=?", (model_id,))
        return self.get_external_model(model_id)

    def deactivate_external_model(self, project_id: str, model_id: str) -> dict[str, Any]:
        model = self.get_external_model(model_id)
        if model["project_id"] != project_id:
            raise VideoResourceNotFoundError("External model not found in project")
        self.execute("UPDATE external_models SET is_active=0 WHERE external_model_id=?", (model_id,))
        return self.get_external_model(model_id)

    def replace_model_predictions(
        self,
        model_id: str,
        video_id: str,
        predictions: Sequence[dict[str, Any]],
        suggestions: Sequence[dict[str, Any]],
    ) -> None:
        with self.connection() as connection, connection:
            window_ids = [row[0] for row in connection.execute("SELECT window_id FROM generated_windows WHERE video_id=?", (video_id,))]
            if window_ids:
                placeholders = ",".join("?" for _ in window_ids)
                connection.execute(
                    f"DELETE FROM model_window_predictions WHERE external_model_id=? AND window_id IN ({placeholders})",
                    [model_id, *window_ids],
                )
            connection.execute(
                "DELETE FROM model_suggestions WHERE external_model_id=? AND video_id=? AND review_status='pending'",
                (model_id, video_id),
            )
            for prediction in predictions:
                fields = ["prediction_id", "external_model_id", *prediction.keys()]
                connection.execute(
                    f"INSERT INTO model_window_predictions({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                    [uuid4().hex, model_id, *prediction.values()],
                )
            for suggestion in suggestions:
                fields = ["suggestion_id", "external_model_id", "video_id", *suggestion.keys()]
                connection.execute(
                    f"INSERT INTO model_suggestions({','.join(fields)}) VALUES ({','.join('?' for _ in fields)})",
                    [uuid4().hex, model_id, video_id, *suggestion.values()],
                )

    def create_export(self, project_id: str) -> dict[str, Any]:
        export_id = uuid4().hex
        self.execute("INSERT INTO video_exports(export_id,project_id) VALUES (?,?)", (export_id, project_id))
        export = self.one("SELECT * FROM video_exports WHERE export_id=?", (export_id,))
        return export or {}

    def get_export(self, export_id: str) -> dict[str, Any]:
        export = self.one("SELECT * FROM video_exports WHERE export_id=?", (export_id,))
        if export is None:
            raise VideoResourceNotFoundError("Export not found")
        return export

    def list_exports(self, project_id: str) -> list[dict[str, Any]]:
        return self.all("SELECT * FROM video_exports WHERE project_id=? ORDER BY created_at DESC", (project_id,))
