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


VIDEO_SCHEMA_VERSION = 4

# Workspace events are intentionally retained in SQLite rather than memory.
# The API and the processing worker run in separate processes, so an in-memory
# pub/sub object would lose events across restarts and would not cross process
# boundaries. The bounded retention keeps the local database compact while
# allowing reconnecting browsers to recover from short outages.
WORKSPACE_EVENT_RETENTION = 10_000
WORKSPACE_EVENT_RETENTION_HOURS = 24
WORKSPACE_EVENT_BATCH_SIZE = 500
ANNOTATION_DERIVATIVE_STAGE = "annotation_derivatives"
ANNOTATION_DERIVATIVE_PRIORITY = 250

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
    "payload_json",
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
            if 3 not in applied:
                self._migrate_v3(connection)
                connection.execute(
                    "INSERT INTO video_schema_migrations(version) VALUES (3)"
                )
            if 4 not in applied:
                self._migrate_v4(connection)
                connection.execute(
                    "INSERT INTO video_schema_migrations(version) VALUES (4)"
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
    def _migrate_v3(connection: sqlite3.Connection) -> None:
        """Add the durable, project-scoped workspace event outbox.

        ``video_id`` deliberately has no foreign-key constraint. A video-delete
        event must remain readable after the video row and its dependent rows
        have been removed by SQLite's cascading delete.
        """

        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS video_workspace_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL REFERENCES video_projects(project_id)
                    ON DELETE CASCADE,
                video_id TEXT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_workspace_events_project_event
                ON video_workspace_events(project_id, event_id);
            """
        )

    @staticmethod
    def _migrate_v4(connection: sqlite3.Connection) -> None:
        """Persist revision-aware annotation derivative refresh requests.

        A request survives while a suggestion pipeline is active, then becomes
        a distinct worker stage after that pipeline finishes. This prevents a
        label edit from being accidentally coalesced into Threshold or model
        inference work.
        """

        columns = {
            str(row[1])
            for row in connection.execute("PRAGMA table_info(processing_jobs)")
        }
        if "annotation_revision" not in columns:
            connection.execute(
                "ALTER TABLE processing_jobs ADD COLUMN annotation_revision INTEGER"
            )
        connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS annotation_derivative_refreshes (
                video_id TEXT PRIMARY KEY REFERENCES videos(video_id)
                    ON DELETE CASCADE,
                project_id TEXT NOT NULL REFERENCES video_projects(project_id)
                    ON DELETE CASCADE,
                requested_revision INTEGER NOT NULL,
                requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE INDEX IF NOT EXISTS idx_derivative_refreshes_project
                ON annotation_derivative_refreshes(project_id, requested_at);
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

    @staticmethod
    def _public_workspace_event(event: dict[str, Any]) -> dict[str, Any]:
        """Return the stable wire representation without persistence fields."""

        return {
            "event_id": int(event["event_id"]),
            "project_id": str(event["project_id"]),
            "video_id": event.get("video_id"),
            "event_type": str(event["event_type"]),
            "payload": event.get("payload", {}),
            "created_at": str(event["created_at"]),
        }

    @staticmethod
    def _job_event_payload(job: dict[str, Any]) -> dict[str, Any]:
        """Keep job events compact and aligned with the existing job API."""

        fields = (
            "job_id",
            "project_id",
            "video_id",
            "stage",
            "status",
            "priority",
            "progress",
            "target_mode",
            "external_model_id",
            "error_message",
            "updated_at",
        )
        return {"job": {field: job.get(field) for field in fields}}

    @staticmethod
    def _job_event_is_meaningful(
        previous: dict[str, Any],
        current: dict[str, Any],
        changed_values: dict[str, Any],
    ) -> bool:
        """Suppress heartbeat-only events and coalesce noisy progress writes."""

        visible_fields = (
            "stage",
            "status",
            "priority",
            "target_mode",
            "external_model_id",
            "error_message",
            "control_requested",
        )
        if any(previous.get(field) != current.get(field) for field in visible_fields):
            return True
        if "progress" not in changed_values:
            return False
        previous_progress = float(previous.get("progress") or 0)
        current_progress = float(current.get("progress") or 0)
        return current_progress >= 0.999 or abs(current_progress - previous_progress) >= 0.01

    @staticmethod
    def _video_event_payload(
        video: dict[str, Any] | None,
        *,
        video_id: str | None = None,
        deleted: bool = False,
    ) -> dict[str, Any]:
        """Represent one changed video without publishing a full project list."""

        identifier = video_id or (str(video["video_id"]) if video else None)
        payload: dict[str, Any] = {
            "video_id": identifier,
            "deleted": deleted,
        }
        if video is not None:
            payload["video"] = video
        return payload

    @staticmethod
    def _export_event_payload(export: dict[str, Any]) -> dict[str, Any]:
        """Return export state without repeatedly sending its full manifest."""

        fields = (
            "export_id",
            "project_id",
            "job_id",
            "status",
            "artifact_path",
            "validation",
            "created_at",
            "finished_at",
        )
        return {"export": {field: export.get(field) for field in fields}}

    def _emit_workspace_event(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        event_type: str,
        payload: dict[str, Any],
        *,
        video_id: str | None = None,
    ) -> int:
        """Write an outbox event using the caller's active transaction.

        All public mutation methods call this helper before committing their
        state change. This makes the event durable and prevents a completed
        worker action from becoming invisible to an already-open workspace.
        """

        cursor = connection.execute(
            """
            INSERT INTO video_workspace_events(
                project_id, video_id, event_type, payload_json
            ) VALUES (?, ?, ?, ?)
            """,
            (
                project_id,
                video_id,
                event_type,
                json.dumps(payload, separators=(",", ":"), sort_keys=True),
            ),
        )
        event_id = int(cursor.lastrowid)
        # The indexed existence check enforces the hard per-project count
        # bound. Periodic pruning also removes events older than the time
        # window without adding a delete to every worker progress write.
        over_count_limit = bool(
            connection.execute(
                """
                SELECT EXISTS(
                    SELECT 1 FROM video_workspace_events
                    WHERE project_id=?
                    LIMIT 1 OFFSET ?
                )
                """,
                (project_id, WORKSPACE_EVENT_RETENTION),
            ).fetchone()[0]
        )
        if over_count_limit or event_id % 100 == 0:
            self._prune_workspace_events(connection, project_id)
        return event_id

    def _emit_annotation_changed(
        self,
        connection: sqlite3.Connection,
        video_id: str,
        reason: str,
    ) -> dict[str, Any]:
        """Publish a compact annotation invalidation without full segment data.

        Segment and track payloads can be large enough to make event streaming
        counterproductive. Clients receive the revision and re-read only the
        currently open video's tracks/segments when necessary. The annotation
        summary fields are sufficient to update a sidebar card without a second
        full ``video.changed`` event for every small edit.
        """

        row = connection.execute(
            "SELECT * FROM videos WHERE video_id=?", (video_id,)
        ).fetchone()
        if row is None:
            raise VideoResourceNotFoundError("Video not found")
        video = self._decode(row) or {}
        project_id = str(video["project_id"])
        self._emit_workspace_event(
            connection,
            project_id,
            "annotation.changed",
            {
                "video_id": video_id,
                "annotation_revision": int(video["annotation_revision"]),
                "annotation_status": video["annotation_status"],
                "is_approved": bool(video["is_approved"]),
                "approval_revision": video.get("approval_revision"),
                "reason": reason,
            },
            video_id=video_id,
        )
        return video

    def publish_annotation_changed(self, video_id: str, reason: str) -> None:
        """Publish a post-transaction notification for a composed edit.

        Most annotation repository methods emit inside their own transaction.
        This public helper is reserved for legacy callers that have already
        committed their state. New persistence operations should emit within
        their primary transaction so state and outbox rows stay atomic.
        """

        with self.connection() as connection, connection:
            self._emit_annotation_changed(connection, video_id, reason)

    def publish_tracks_changed(self, video_id: str, reason: str) -> None:
        """Publish one compact worker-list invalidation for a composed edit.

        Atomic manual track mutations emit this event in their own repository
        transaction. This compatibility helper is only for legacy callers that
        already committed their state and need a compact remote refresh.
        """

        with self.connection() as connection, connection:
            self._emit_tracks_changed(connection, video_id, reason)

    def _invalidate_track_derivatives_in_transaction(
        self,
        connection: sqlite3.Connection,
        video_id: str,
        track_ids: set[int],
    ) -> None:
        """Drop dependent rows for changed workers while the writer lock is held."""

        if not track_ids:
            return
        placeholders = ",".join("?" for _ in track_ids)
        values = [video_id, *sorted(track_ids)]
        for table in (
            "threshold_suggestions",
            "model_suggestions",
            "generated_windows",
        ):
            connection.execute(
                f"DELETE FROM {table} WHERE video_id=? AND track_id IN ({placeholders})",
                values,
            )

    @staticmethod
    def _assert_expected_pose_cache_version(
        connection: sqlite3.Connection,
        video_id: str,
        expected_pose_cache_version: str | None,
    ) -> None:
        """Reject a staged pose pointer if another edit already replaced it."""

        if expected_pose_cache_version is None:
            return
        row = connection.execute(
            "SELECT pose_cache_version FROM videos WHERE video_id=?",
            (video_id,),
        ).fetchone()
        if row is None:
            raise VideoResourceNotFoundError("Video not found")
        if row["pose_cache_version"] != expected_pose_cache_version:
            raise RevisionConflictError(
                "Pose data changed while this worker edit was being applied. "
                "Please try the edit again."
            )

    def _finalize_track_mutation_in_transaction(
        self,
        connection: sqlite3.Connection,
        video_id: str,
        reason: str,
        *,
        pose_cache_version: str | None = None,
    ) -> dict[str, Any]:
        """Advance the durable annotation input revision for one track edit.

        Callers must have already changed the worker rows and invalidated their
        direct dependants in the same ``BEGIN IMMEDIATE`` transaction. This
        finalizer makes the revision, optional staged pose pointer, derivative
        intent, and outbox events one commit, so a worker never publishes
        artifacts for a mixed track shape.
        """

        row = connection.execute(
            "SELECT * FROM videos WHERE video_id=?",
            (video_id,),
        ).fetchone()
        if row is None:
            raise VideoResourceNotFoundError("Video not found")
        video = self._decode(row) or {}
        revision = int(video["annotation_revision"]) + 1
        has_segments = connection.execute(
            "SELECT 1 FROM video_segments WHERE video_id=? LIMIT 1",
            (video_id,),
        ).fetchone()
        annotation_status = "labeled" if has_segments is not None else "unlabeled"
        connection.execute(
            """
            UPDATE videos
            SET annotation_revision=?,
                is_approved=0,
                approval_revision=NULL,
                approved_at=NULL,
                annotation_status=?,
                pose_cache_version=COALESCE(?, pose_cache_version),
                feature_cache_version=NULL,
                threshold_cache_version=NULL,
                window_cache_version=NULL,
                updated_at=CURRENT_TIMESTAMP
            WHERE video_id=?
            """,
            (revision, annotation_status, pose_cache_version, video_id),
        )
        connection.execute(
            """
            UPDATE generated_windows
            SET stale=1, feature_status='pending', updated_at=CURRENT_TIMESTAMP
            WHERE video_id=?
            """,
            (video_id,),
        )
        # Do not delete the old feature file here. The null cache version above
        # makes it unreachable, while the queued derivative worker publishes
        # its replacement atomically without a cross-process delete/write race.
        self._emit_annotation_changed(connection, video_id, reason)
        self._schedule_annotation_derivatives_if_ready(
            connection,
            video_id,
            revision,
        )
        self._emit_tracks_changed(connection, video_id, reason)
        updated = connection.execute(
            "SELECT * FROM videos WHERE video_id=?",
            (video_id,),
        ).fetchone()
        return self._decode(updated) or {}

    def publish_track_mutation(self, video_id: str, reason: str) -> dict[str, Any]:
        """Finalize a legacy pre-committed track edit as one revision event.

        New track operations use the atomic repository methods below. This
        compatibility helper remains for callers that have no row mutation to
        perform, but it is intentionally not used by the annotation service.
        """

        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                updated = self._finalize_track_mutation_in_transaction(
                    connection,
                    video_id,
                    reason,
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return updated

    def _emit_tracks_changed(
        self,
        connection: sqlite3.Connection,
        video_id: str,
        reason: str,
    ) -> None:
        """Publish a track-only invalidation with its current annotation revision."""

        row = connection.execute(
            """
            SELECT project_id, annotation_revision, annotation_status,
                   is_approved, approval_revision
            FROM videos WHERE video_id=?
            """,
            (video_id,),
        ).fetchone()
        if row is None:
            raise VideoResourceNotFoundError("Video not found")
        self._emit_workspace_event(
            connection,
            str(row["project_id"]),
            "tracks.changed",
            {
                "video_id": video_id,
                "annotation_revision": int(row["annotation_revision"]),
                "annotation_status": row["annotation_status"],
                "is_approved": bool(row["is_approved"]),
                "approval_revision": row["approval_revision"],
                "reason": reason,
            },
            video_id=video_id,
        )

    @staticmethod
    def _prune_workspace_events(
        connection: sqlite3.Connection,
        project_id: str,
    ) -> None:
        """Retain recent events by age and by per-project count."""

        connection.execute(
            """
            DELETE FROM video_workspace_events
            WHERE project_id=?
              AND created_at < datetime('now', ?)
            """,
            (project_id, f"-{WORKSPACE_EVENT_RETENTION_HOURS} hours"),
        )
        connection.execute(
            """
            DELETE FROM video_workspace_events
            WHERE event_id IN (
                SELECT event_id
                FROM video_workspace_events
                WHERE project_id=?
                ORDER BY event_id DESC
                LIMIT -1 OFFSET ?
            )
            """,
            (project_id, WORKSPACE_EVENT_RETENTION),
        )

    def one(self, sql: str, values: Sequence[Any] = ()) -> dict[str, Any] | None:
        with self.connection() as connection:
            return self._decode(connection.execute(sql, values).fetchone())

    def all(self, sql: str, values: Sequence[Any] = ()) -> list[dict[str, Any]]:
        with self.connection() as connection:
            return [self._decode(row) or {} for row in connection.execute(sql, values).fetchall()]

    def execute(self, sql: str, values: Sequence[Any] = ()) -> None:
        with self.connection() as connection, connection:
            connection.execute(sql, values)

    def latest_workspace_event_id(self, project_id: str) -> int:
        """Return the latest durable event cursor for one project."""

        self.get_project(project_id)
        row = self.one(
            """
            SELECT COALESCE(MAX(event_id), 0) AS event_id
            FROM video_workspace_events
            WHERE project_id=?
            """,
            (project_id,),
        )
        return int((row or {}).get("event_id", 0))

    def workspace_event_changes(
        self,
        project_id: str,
        after: int,
        *,
        limit: int = WORKSPACE_EVENT_BATCH_SIZE,
    ) -> dict[str, Any]:
        """Return a bounded event delta or request a snapshot resynchronization.

        Cursors are project-local from the client's perspective even though the
        SQLite primary key is global. If retention removed the requested cursor,
        a partial delta could leave the UI inconsistent, so callers receive a
        deterministic ``resync_required`` signal instead.
        """

        if after < 0:
            raise ValueError("Workspace event cursor cannot be negative")
        if limit < 1:
            raise ValueError("Workspace event limit must be positive")

        self.get_project(project_id)
        batch_limit = min(limit, WORKSPACE_EVENT_BATCH_SIZE)
        with self.connection() as connection:
            bounds = connection.execute(
                """
                SELECT MIN(event_id) AS oldest_event_id,
                       MAX(event_id) AS newest_event_id
                FROM video_workspace_events
                WHERE project_id=?
                """,
                (project_id,),
            ).fetchone()
            oldest = int(bounds["oldest_event_id"]) if bounds and bounds["oldest_event_id"] is not None else 0
            newest = int(bounds["newest_event_id"]) if bounds and bounds["newest_event_id"] is not None else 0
            if after > 0 and oldest and after < oldest - 1:
                return {
                    "events": [],
                    "last_event_id": newest,
                    "resync_required": True,
                    "has_more": False,
                }
            rows = connection.execute(
                """
                SELECT * FROM video_workspace_events
                WHERE project_id=? AND event_id > ?
                ORDER BY event_id
                LIMIT ?
                """,
                (project_id, after, batch_limit + 1),
            ).fetchall()

        has_more = len(rows) > batch_limit
        rows = rows[:batch_limit]
        events = [self._public_workspace_event(self._decode(row) or {}) for row in rows]
        cursor = int(events[-1]["event_id"]) if events else max(after, newest)
        return {
            "events": events,
            "last_event_id": cursor,
            "resync_required": False,
            "has_more": has_more,
        }

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
            row = connection.execute(
                "SELECT * FROM videos WHERE video_id=?", (video_id,)
            ).fetchone()
            video = self._decode(row) or {}
            self._emit_workspace_event(
                connection,
                project_id,
                "video.changed",
                self._video_event_payload(video),
                video_id=video_id,
            )
        return video

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
        assignments = ",".join(f"{key}=?" for key in values)
        with self.connection() as connection, connection:
            current = connection.execute(
                "SELECT project_id FROM videos WHERE video_id=?", (video_id,)
            ).fetchone()
            if current is None:
                raise VideoResourceNotFoundError("Video not found")
            connection.execute(
                f"UPDATE videos SET {assignments}, updated_at=CURRENT_TIMESTAMP WHERE video_id=?",
                [*values.values(), video_id],
            )
            row = connection.execute(
                "SELECT * FROM videos WHERE video_id=?", (video_id,)
            ).fetchone()
            video = self._decode(row) or {}
            self._emit_workspace_event(
                connection,
                str(current["project_id"]),
                "video.changed",
                self._video_event_payload(video),
                video_id=video_id,
            )
        return video

    def invalidate_annotation_derivatives(self, video_id: str) -> dict[str, Any]:
        """Mark windows and label-bearing feature artifacts stale atomically.

        Raw pose data remains valid after an annotation edit, but generated
        windows and feature artifacts include human labels. Clearing their
        cache versions prevents an interrupted derivative job from being
        mistaken for a fresh training-data artifact.
        """

        with self.connection() as connection, connection:
            existing = connection.execute(
                "SELECT project_id FROM videos WHERE video_id=?", (video_id,)
            ).fetchone()
            if existing is None:
                raise VideoResourceNotFoundError("Video not found")
            connection.execute(
                """
                UPDATE generated_windows
                SET stale=1, feature_status='pending', updated_at=CURRENT_TIMESTAMP
                WHERE video_id=?
                """,
                (video_id,),
            )
            connection.execute(
                """
                UPDATE videos
                SET feature_cache_version=NULL,
                    window_cache_version=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE video_id=?
                """,
                (video_id,),
            )
            row = connection.execute(
                "SELECT * FROM videos WHERE video_id=?", (video_id,)
            ).fetchone()
            video = self._decode(row) or {}
            self._emit_workspace_event(
                connection,
                str(existing["project_id"]),
                "video.changed",
                self._video_event_payload(video),
                video_id=video_id,
            )
        return video

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
            self._emit_workspace_event(
                connection,
                project_id,
                "video.changed",
                self._video_event_payload(
                    None,
                    video_id=video_id,
                    deleted=True,
                ),
                video_id=video_id,
            )
            connection.execute(
                "DELETE FROM videos WHERE project_id=? AND video_id=?",
                (project_id, video_id),
            )
        return self._decode(row) or {}

    def rename_videos(self, project_id: str, filename_map: dict[str, str]) -> None:
        """Atomically update display filenames for videos in one project."""

        with self.connection() as connection, connection:
            for video_id, filename in filename_map.items():
                updated = connection.execute(
                    "UPDATE videos SET filename=?, updated_at=CURRENT_TIMESTAMP WHERE project_id=? AND video_id=?",
                    (filename, project_id, video_id),
                )
                if updated.rowcount != 1:
                    raise VideoResourceNotFoundError("Video not found in project")
                row = connection.execute(
                    "SELECT * FROM videos WHERE video_id=?", (video_id,)
                ).fetchone()
                video = self._decode(row) or {}
                self._emit_workspace_event(
                    connection,
                    project_id,
                    "video.changed",
                    self._video_event_payload(video),
                    video_id=video_id,
                )

    def replace_frame_mapping(self, video_id: str, mapping: Sequence[tuple[int, int, float]]) -> None:
        with self.connection() as connection, connection:
            connection.execute("DELETE FROM canonical_frame_mappings WHERE video_id=?", (video_id,))
            connection.executemany(
                "INSERT INTO canonical_frame_mappings(video_id,canonical_frame,original_frame,timestamp_seconds) VALUES (?,?,?,?)",
                [(video_id, *row) for row in mapping],
            )

    def reset_trimmed_video(
        self,
        video_id: str,
        values: dict[str, Any],
        mapping: Sequence[tuple[int, int, float]],
    ) -> dict[str, Any]:
        """Discard frame-dependent state after replacing a video's media.

        Tracks, labels, suggestions, jobs, and history point at the old frame
        sequence. Keeping any of them after a destructive trim would make the
        annotation data incorrect, so the replacement starts as a clean import.
        """

        with self.connection() as connection, connection:
            if connection.execute("SELECT 1 FROM videos WHERE video_id=?", (video_id,)).fetchone() is None:
                raise VideoResourceNotFoundError("Video not found")
            for table in (
                "processing_jobs",
                "video_tracks",
                "video_segments",
                "annotation_history",
                "generated_windows",
                "threshold_suggestions",
                "model_suggestions",
                "canonical_frame_mappings",
            ):
                connection.execute(f"DELETE FROM {table} WHERE video_id=?", (video_id,))
            assignments = ",".join(f"{field}=?" for field in values)
            connection.execute(
                f"""
                UPDATE videos
                SET {assignments},
                    processing_status='imported',
                    annotation_status='unlabeled',
                    quality_status='unknown',
                    annotation_revision=0,
                    is_approved=0,
                    approval_revision=NULL,
                    approved_at=NULL,
                    pose_cache_version=NULL,
                    tracking_cache_version=NULL,
                    feature_cache_version=NULL,
                    threshold_cache_version=NULL,
                    window_cache_version=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE video_id=?
                """,
                [*values.values(), video_id],
            )
            connection.executemany(
                "INSERT INTO canonical_frame_mappings(video_id,canonical_frame,original_frame,timestamp_seconds) VALUES (?,?,?,?)",
                [(video_id, *row) for row in mapping],
            )
            connection.execute(
                """
                UPDATE video_workspace_state
                SET track_id=NULL, frame_index=0, updated_at=CURRENT_TIMESTAMP
                WHERE video_id=?
                """,
                (video_id,),
            )
            row = connection.execute(
                "SELECT * FROM videos WHERE video_id=?", (video_id,)
            ).fetchone()
            video = self._decode(row) or {}
            self._emit_workspace_event(
                connection,
                str(video["project_id"]),
                "video.changed",
                self._video_event_payload(video),
                video_id=video_id,
            )
            self._emit_annotation_changed(
                connection,
                video_id,
                "trimmed_video_reset",
            )
        return video

    def trimmed_annotation_snapshot(
        self, video_id: str, start_frame: int, end_frame: int
    ) -> dict[str, list[dict[str, Any]]]:
        """Return tracks and segments intersecting an inclusive trim range."""

        self.get_video(video_id)
        tracks = [
            track for track in self.list_tracks(video_id)
            if int(track["start_frame"]) <= end_frame and int(track["end_frame"]) >= start_frame
        ]
        segments = [
            segment for segment in self.list_segments(video_id)
            if int(segment["start_frame"]) <= end_frame and int(segment["end_frame"]) >= start_frame
        ]
        return {"tracks": tracks, "segments": segments}

    def restore_trimmed_annotations(
        self,
        video_id: str,
        snapshot: dict[str, list[dict[str, Any]]],
        start_frame: int,
        end_frame: int,
    ) -> None:
        """Restore clipped labels at frame zero after a media trim.

        Pose data and suggestions are intentionally not restored. These rows
        keep only user-visible annotation state whose frame coordinates can be
        safely translated to the newly saved video.
        """

        with self.connection() as connection, connection:
            connection.execute("DELETE FROM video_tracks WHERE video_id=?", (video_id,))
            connection.execute("DELETE FROM video_segments WHERE video_id=?", (video_id,))
            connection.execute("DELETE FROM annotation_history WHERE video_id=?", (video_id,))
            for track in snapshot["tracks"]:
                clipped_start = max(int(track["start_frame"]), start_frame) - start_frame
                clipped_end = min(int(track["end_frame"]), end_frame) - start_frame
                length = clipped_end - clipped_start + 1
                valid = min(length, int(track["valid_frame_count"]))
                connection.execute(
                    """
                    INSERT INTO video_tracks(
                        track_pk,video_id,track_id,start_frame,end_frame,
                        valid_frame_count,gap_count,avg_person_confidence,
                        avg_keypoint_confidence,valid_frame_ratio,
                        missing_ankle_ratio,quality_status,include_in_export,
                        exclude_reason,revision
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        uuid4().hex, video_id, track["track_id"], clipped_start,
                        clipped_end, valid, min(length - valid, int(track["gap_count"])),
                        track["avg_person_confidence"], track["avg_keypoint_confidence"],
                        track["valid_frame_ratio"], track["missing_ankle_ratio"],
                        track["quality_status"], track["include_in_export"],
                        track["exclude_reason"], 1,
                    ),
                )
            for segment in snapshot["segments"]:
                connection.execute(
                    """
                    INSERT INTO video_segments(
                        segment_id,video_id,track_id,start_frame,end_frame,label,
                        quality_status,include_in_export,exclude_reason,
                        annotation_version,source_type,source_id,created_by
                    ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                    """,
                    (
                        uuid4().hex, video_id, segment["track_id"],
                        max(int(segment["start_frame"]), start_frame) - start_frame,
                        min(int(segment["end_frame"]), end_frame) - start_frame,
                        segment["label"], segment["quality_status"],
                        segment["include_in_export"], segment["exclude_reason"],
                        1, segment["source_type"], segment["source_id"],
                        segment["created_by"],
                    ),
                )
            has_labels = bool(snapshot["segments"])
            connection.execute(
                """
                UPDATE videos
                SET annotation_revision=?, annotation_status=?, is_approved=0,
                    approval_revision=NULL, approved_at=NULL,
                    updated_at=CURRENT_TIMESTAMP
                WHERE video_id=?
                """,
                (1 if has_labels else 0, "labeled" if has_labels else "unlabeled", video_id),
            )
            row = connection.execute(
                "SELECT * FROM videos WHERE video_id=?", (video_id,)
            ).fetchone()
            video = self._decode(row) or {}
            self._emit_workspace_event(
                connection,
                str(video["project_id"]),
                "video.changed",
                self._video_event_payload(video),
                video_id=video_id,
            )
            self._emit_annotation_changed(
                connection,
                video_id,
                "trimmed_annotations_restored",
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
        job_id = uuid4().hex
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            existing = connection.execute(
                """
                SELECT * FROM processing_jobs
                WHERE project_id=? AND video_id IS ? AND stage=?
                  AND status IN ('queued','running','paused')
                ORDER BY created_at DESC LIMIT 1
                """,
                (project_id, video_id, stage),
            ).fetchone()
            if existing is not None:
                connection.commit()
                return self._decode(existing) or {}
            connection.execute(
                "INSERT INTO processing_jobs(job_id,project_id,video_id,stage,priority) VALUES (?,?,?,?,?)",
                (job_id, project_id, video_id, stage, priority),
            )
            row = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            job = self._decode(row) or {}
            self._emit_workspace_event(
                connection,
                project_id,
                "job.changed",
                self._job_event_payload(job),
                video_id=None,
            )
            connection.commit()
        return job

    def enqueue_pipeline_job(
        self,
        project_id: str,
        video_id: str,
        stage: str,
        target_mode: str,
        external_model_id: str | None,
        priority: int = 100,
        *,
        annotation_revision: int | None = None,
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
                "SELECT project_id, annotation_revision FROM videos WHERE video_id=?",
                (video_id,),
            ).fetchone()
            if video is None or str(video["project_id"]) != project_id:
                raise VideoResourceNotFoundError("Video not found in project")
            if annotation_revision is None:
                annotation_revision = int(video["annotation_revision"])

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
                active_is_derivative = (
                    decoded.get("stage") == ANNOTATION_DERIVATIVE_STAGE
                )
                requested_is_derivative = stage == ANNOTATION_DERIVATIVE_STAGE
                if active_is_derivative != requested_is_derivative:
                    raise VideoProcessingConflictError(
                        "This video already has a different active processing job"
                    )
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
                    target_mode, external_model_id, annotation_revision
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    project_id,
                    video_id,
                    stage,
                    priority,
                    target_mode,
                    external_model_id,
                    annotation_revision,
                ),
            )
            row = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            job = self._decode(row) or {}
            self._emit_workspace_event(
                connection,
                project_id,
                "job.changed",
                self._job_event_payload(job),
                video_id=video_id,
            )
            connection.commit()
        return job

    def _insert_annotation_derivative_job(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        video_id: str,
        annotation_revision: int,
        priority: int,
        *,
        emit_event: bool,
    ) -> dict[str, Any]:
        """Insert the dedicated refresh stage inside an existing transaction."""

        job_id = uuid4().hex
        connection.execute(
            """
            INSERT INTO processing_jobs(
                job_id, project_id, video_id, stage, priority,
                target_mode, external_model_id, annotation_revision
            ) VALUES (?, ?, ?, ?, ?, 'threshold', NULL, ?)
            """,
            (
                job_id,
                project_id,
                video_id,
                ANNOTATION_DERIVATIVE_STAGE,
                priority,
                annotation_revision,
            ),
        )
        row = connection.execute(
            "SELECT * FROM processing_jobs WHERE job_id=?", (job_id,)
        ).fetchone()
        job = self._decode(row) or {}
        if emit_event:
            self._emit_workspace_event(
                connection,
                project_id,
                "job.changed",
                self._job_event_payload(job),
                video_id=video_id,
            )
        return job

    def _request_annotation_derivative_refresh_in_transaction(
        self,
        connection: sqlite3.Connection,
        project_id: str,
        video_id: str,
        annotation_revision: int,
        priority: int,
        *,
        emit_event: bool,
    ) -> dict[str, Any]:
        """Coalesce one derivative intent while the caller owns the lock."""

        connection.execute(
            """
            INSERT INTO annotation_derivative_refreshes(
                video_id, project_id, requested_revision
            ) VALUES (?, ?, ?)
            ON CONFLICT(video_id) DO UPDATE SET
                requested_revision=MAX(
                    annotation_derivative_refreshes.requested_revision,
                    excluded.requested_revision
                ),
                requested_at=CURRENT_TIMESTAMP
            """,
            (video_id, project_id, annotation_revision),
        )
        request = connection.execute(
            """
            SELECT requested_revision
            FROM annotation_derivative_refreshes
            WHERE video_id=?
            """,
            (video_id,),
        ).fetchone()
        requested_revision = int(request["requested_revision"])
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
            active_job = self._decode(active) or {}
            return {
                "requested_revision": requested_revision,
                "status": (
                    "already_queued"
                    if active_job.get("stage") == ANNOTATION_DERIVATIVE_STAGE
                    else "deferred"
                ),
                "job": (
                    active_job
                    if active_job.get("stage") == ANNOTATION_DERIVATIVE_STAGE
                    else None
                ),
            }
        job = self._insert_annotation_derivative_job(
            connection,
            project_id,
            video_id,
            requested_revision,
            priority,
            emit_event=emit_event,
        )
        return {
            "requested_revision": requested_revision,
            "status": "queued",
            "job": job,
        }

    def _schedule_annotation_derivatives_if_ready(
        self,
        connection: sqlite3.Connection,
        video_id: str,
        annotation_revision: int,
        *,
        priority: int = ANNOTATION_DERIVATIVE_PRIORITY,
    ) -> dict[str, Any] | None:
        """Record an edit-derived refresh when pose data can support it.

        Segment and worker mutations own this call so a navigation, reload, or
        failed frontend follow-up cannot leave label-bearing artifacts stale.
        Pre-pose/manual fixture edits intentionally do not create a job because
        a feature refresh could not run yet. A zero-worker mutation still
        queues cleanup once pose data exists, producing a valid empty artifact
        instead of leaving a stale feature cache behind.
        """

        video = connection.execute(
            "SELECT project_id, pose_cache_version FROM videos WHERE video_id=?",
            (video_id,),
        ).fetchone()
        if video is None:
            raise VideoResourceNotFoundError("Video not found")
        if not video["pose_cache_version"]:
            return None
        return self._request_annotation_derivative_refresh_in_transaction(
            connection,
            str(video["project_id"]),
            video_id,
            annotation_revision,
            priority,
            emit_event=True,
        )

    def request_annotation_derivative_refresh(
        self,
        project_id: str,
        video_id: str,
        *,
        priority: int = ANNOTATION_DERIVATIVE_PRIORITY,
    ) -> dict[str, Any]:
        """Persist one revision-aware derivative request without inference work.

        The per-video request row coalesces repeated annotation edits. If a
        Threshold or model job is active, the request is deferred instead of
        being returned as though it were that suggestion job. The final active
        stage atomically queues this distinct refresh after it completes.
        """

        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            video = connection.execute(
                """
                SELECT project_id, annotation_revision
                FROM videos WHERE video_id=?
                """,
                (video_id,),
            ).fetchone()
            if video is None or str(video["project_id"]) != project_id:
                raise VideoResourceNotFoundError("Video not found in project")
            result = self._request_annotation_derivative_refresh_in_transaction(
                connection,
                project_id,
                video_id,
                int(video["annotation_revision"]),
                priority,
                emit_event=True,
            )
            connection.commit()
        return result

    def supersede_queued_annotation_derivative_refresh(
        self,
        project_id: str,
        video_id: str,
    ) -> dict[str, Any] | None:
        """Retire queued maintenance work before an explicit overwrite run.

        A confirmed Threshold/Model overwrite is user-directed work and takes
        precedence over a queued or paused derivative refresh. A running
        derivative is left intact because it may be writing artifacts; callers
        receive a clear conflict before they clear any labels.
        """

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
            if active is None:
                # A failed/cancelled derivative can leave its coalesced intent
                # behind for a later retry. An explicit overwrite replaces that
                # maintenance intent as well.
                connection.execute(
                    "DELETE FROM annotation_derivative_refreshes WHERE video_id=?",
                    (video_id,),
                )
                connection.commit()
                return None
            if active["stage"] != ANNOTATION_DERIVATIVE_STAGE:
                connection.commit()
                return None
            if active["status"] == "running":
                raise VideoProcessingConflictError(
                    "A derivative refresh is running. Wait for it to finish before "
                    "overwriting labels with new suggestions."
                )
            connection.execute(
                """
                UPDATE processing_jobs
                SET status='cancelled',
                    control_requested=NULL,
                    finished_at=CURRENT_TIMESTAMP,
                    updated_at=CURRENT_TIMESTAMP
                WHERE job_id=?
                """,
                (active["job_id"],),
            )
            row = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?",
                (active["job_id"],),
            ).fetchone()
            retired = self._decode(row) or {}
            connection.execute(
                "DELETE FROM annotation_derivative_refreshes WHERE video_id=?",
                (video_id,),
            )
            self._emit_workspace_event(
                connection,
                project_id,
                "job.changed",
                self._job_event_payload(retired),
                video_id=video_id,
            )
            connection.commit()
        return retired

    def _enqueue_pending_annotation_derivative_after_terminal_stage(
        self,
        connection: sqlite3.Connection,
        terminal_job: sqlite3.Row,
    ) -> sqlite3.Row | None:
        """Resolve a durable edit request after a stage cannot continue.

        Callers use this only once a stage has no successor: after a successful
        final stage or after a Threshold/model pipeline is failed or cancelled.
        The latter matters because a reviewer edit must not stay stale simply
        because unrelated suggestion inference did not finish.
        """

        video_id = terminal_job["video_id"]
        if video_id is None:
            return None
        request = connection.execute(
            """
            SELECT requested_revision
            FROM annotation_derivative_refreshes
            WHERE video_id=?
            """,
            (video_id,),
        ).fetchone()
        if request is None:
            return None
        video = connection.execute(
            """
            SELECT project_id, annotation_revision
            FROM videos WHERE video_id=?
            """,
            (video_id,),
        ).fetchone()
        if video is None:
            return None
        desired_revision = max(
            int(request["requested_revision"]),
            int(video["annotation_revision"]),
        )
        if terminal_job["stage"] == ANNOTATION_DERIVATIVE_STAGE:
            completed_revision = int(terminal_job["annotation_revision"] or -1)
            if completed_revision >= desired_revision:
                connection.execute(
                    "DELETE FROM annotation_derivative_refreshes WHERE video_id=?",
                    (video_id,),
                )
                return None
        inserted = self._insert_annotation_derivative_job(
            connection,
            str(video["project_id"]),
            str(video_id),
            desired_revision,
            max(ANNOTATION_DERIVATIVE_PRIORITY, int(terminal_job["priority"])),
            emit_event=False,
        )
        return connection.execute(
            "SELECT * FROM processing_jobs WHERE job_id=?", (inserted["job_id"],)
        ).fetchone()

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
            claimed = self._decode(
                connection.execute(
                    "SELECT * FROM processing_jobs WHERE job_id=?", (row["job_id"],)
                ).fetchone()
            ) or {}
            self._emit_workspace_event(
                connection,
                str(claimed["project_id"]),
                "job.changed",
                self._job_event_payload(claimed),
                video_id=claimed.get("video_id"),
            )
            return claimed

    def update_job(self, job_id: str, **values: Any) -> dict[str, Any]:
        if "log" in values:
            values["log_json"] = json.dumps(values.pop("log"))
        assignments = ",".join(f"{key}=?" for key in values)
        if not assignments:
            return self.get_job(job_id)
        with self.connection() as connection, connection:
            before_row = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            if before_row is None:
                raise VideoResourceNotFoundError("Processing job not found")
            before = self._decode(before_row) or {}
            connection.execute(
                f"UPDATE processing_jobs SET {assignments},heartbeat_at=CURRENT_TIMESTAMP,updated_at=CURRENT_TIMESTAMP WHERE job_id=?",
                [*values.values(), job_id],
            )
            after_row = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?", (job_id,)
            ).fetchone()
            job = self._decode(after_row) or {}
            derivative_row: sqlite3.Row | None = None
            terminal_status = str(values.get("status") or "")
            if (
                terminal_status in {"failed", "cancelled"}
                and str(before.get("status")) in {"queued", "running", "paused"}
                and job.get("stage") != ANNOTATION_DERIVATIVE_STAGE
            ):
                # A label refresh can be deferred behind an active suggestion
                # pipeline. If that pipeline ends unsuccessfully, promote the
                # intent in this same transaction rather than leaving edited
                # training/export derivatives stale until another UI action.
                derivative_row = self._enqueue_pending_annotation_derivative_after_terminal_stage(
                    connection,
                    after_row,
                )
            if self._job_event_is_meaningful(before, job, values):
                self._emit_workspace_event(
                    connection,
                    str(job["project_id"]),
                    "job.changed",
                    self._job_event_payload(job),
                    video_id=job.get("video_id"),
                )
            derivative_job = self._decode(derivative_row)
            if derivative_job is not None:
                self._emit_workspace_event(
                    connection,
                    str(derivative_job["project_id"]),
                    "job.changed",
                    self._job_event_payload(derivative_job),
                    video_id=derivative_job.get("video_id"),
                )
        return job

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
                        target_mode, external_model_id, annotation_revision
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        next_id,
                        row["project_id"],
                        row["video_id"],
                        next_stage,
                        # Keep one video's dependent stages ahead of other
                        # queued videos. This lets a completed pipeline become
                        # annotation-ready immediately instead of processing
                        # every video one stage at a time.
                        int(row["priority"]) + 1,
                        row["target_mode"],
                        row["external_model_id"],
                        row["annotation_revision"],
                    ),
                )
                next_row = connection.execute(
                    "SELECT * FROM processing_jobs WHERE job_id=?",
                    (next_id,),
                ).fetchone()
            else:
                next_row = self._enqueue_pending_annotation_derivative_after_terminal_stage(
                    connection,
                    row,
                )
            completed = connection.execute(
                "SELECT * FROM processing_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            completed_job = self._decode(completed) or {}
            self._emit_workspace_event(
                connection,
                str(completed_job["project_id"]),
                "job.changed",
                self._job_event_payload(completed_job),
                video_id=completed_job.get("video_id"),
            )
            decoded_next = self._decode(next_row)
            if decoded_next is not None:
                self._emit_workspace_event(
                    connection,
                    str(decoded_next["project_id"]),
                    "job.changed",
                    self._job_event_payload(decoded_next),
                    video_id=decoded_next.get("video_id"),
                )
            connection.commit()
        return completed_job, decoded_next

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
            retried_job = self._decode(retried) or {}
            self._emit_workspace_event(
                connection,
                str(retried_job["project_id"]),
                "job.changed",
                self._job_event_payload(retried_job),
                video_id=retried_job.get("video_id"),
            )
            connection.commit()
        return retried_job

    def recover_stale_jobs(self, stale_seconds: int = 60) -> int:
        with self.connection() as connection, connection:
            stale_rows = connection.execute(
                """
                SELECT job_id FROM processing_jobs
                WHERE status='running'
                  AND (heartbeat_at IS NULL OR heartbeat_at <= datetime('now', ?))
                """,
                (f"-{max(1, stale_seconds)} seconds",),
            ).fetchall()
            cursor = connection.execute(
                "UPDATE processing_jobs SET status='queued',worker_id=NULL,control_requested=NULL,error_message='Recovered after stale worker heartbeat',updated_at=CURRENT_TIMESTAMP WHERE status='running' AND (heartbeat_at IS NULL OR heartbeat_at <= datetime('now', ?))",
                (f"-{max(1, stale_seconds)} seconds",),
            )
            for stale in stale_rows:
                row = connection.execute(
                    "SELECT * FROM processing_jobs WHERE job_id=?", (stale["job_id"],)
                ).fetchone()
                job = self._decode(row) or {}
                self._emit_workspace_event(
                    connection,
                    str(job["project_id"]),
                    "job.changed",
                    self._job_event_payload(job),
                    video_id=job.get("video_id"),
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
            if connection.execute(
                "SELECT 1 FROM videos WHERE video_id=?", (video_id,)
            ).fetchone() is None:
                raise VideoResourceNotFoundError("Video not found")
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
            self._emit_tracks_changed(connection, video_id, "tracks_replaced")

    def list_tracks(self, video_id: str, include_excluded: bool = True) -> list[dict[str, Any]]:
        self.get_video(video_id)
        clause = "" if include_excluded else " AND include_in_export=1"
        return self.all(f"SELECT * FROM video_tracks WHERE video_id=?{clause} ORDER BY track_id", (video_id,))

    def get_track(self, video_id: str, track_id: int) -> dict[str, Any]:
        track = self.one("SELECT * FROM video_tracks WHERE video_id=? AND track_id=?", (video_id, track_id))
        if track is None:
            raise VideoResourceNotFoundError("Track not found")
        return track

    def update_track(
        self,
        video_id: str,
        track_id: int,
        *,
        emit_event: bool = True,
        **values: Any,
    ) -> dict[str, Any]:
        """Update one worker and optionally finalize a durable manual mutation.

        The annotation service uses the specialized atomic methods below for
        multi-row operations. Keeping the default path revision-aware prevents
        an ad-hoc single-track update from bypassing cache invalidation.
        """

        assignments = ",".join(f"{key}=?" for key in values)
        if not assignments:
            return self.get_track(video_id, track_id)
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    "SELECT * FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, track_id),
                ).fetchone()
                if existing is None:
                    raise VideoResourceNotFoundError("Track not found")
                connection.execute(
                    f"UPDATE video_tracks SET {assignments},revision=revision+1,updated_at=CURRENT_TIMESTAMP WHERE video_id=? AND track_id=?",
                    [*values.values(), video_id, track_id],
                )
                if emit_event:
                    self._invalidate_track_derivatives_in_transaction(
                        connection,
                        video_id,
                        {track_id},
                    )
                    self._finalize_track_mutation_in_transaction(
                        connection,
                        video_id,
                        "track_updated",
                    )
                row = connection.execute(
                    "SELECT * FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, track_id),
                ).fetchone()
                track = self._decode(row) or {}
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return track

    def merge_tracks_atomically(
        self,
        video_id: str,
        target_track_id: int,
        source_track_id: int,
        *,
        pose_cache_version: str | None = None,
        expected_pose_cache_version: str | None = None,
    ) -> dict[str, Any]:
        """Merge two workers with invalidation and revision events in one commit."""

        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._assert_expected_pose_cache_version(
                    connection,
                    video_id,
                    expected_pose_cache_version,
                )
                target = connection.execute(
                    "SELECT * FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, target_track_id),
                ).fetchone()
                source = connection.execute(
                    "SELECT * FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, source_track_id),
                ).fetchone()
                if target is None or source is None:
                    raise VideoResourceNotFoundError("Track not found")
                connection.execute(
                    """
                    UPDATE video_tracks
                    SET start_frame=?,
                        end_frame=?,
                        valid_frame_count=?,
                        quality_status=?,
                        revision=revision+1,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE video_id=? AND track_id=?
                    """,
                    (
                        min(int(target["start_frame"]), int(source["start_frame"])),
                        max(int(target["end_frame"]), int(source["end_frame"])),
                        int(target["valid_frame_count"])
                        + int(source["valid_frame_count"]),
                        target["quality_status"],
                        video_id,
                        target_track_id,
                    ),
                )
                connection.execute(
                    "UPDATE video_segments SET track_id=? "
                    "WHERE video_id=? AND track_id=?",
                    (target_track_id, video_id, source_track_id),
                )
                connection.execute(
                    "DELETE FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, source_track_id),
                )
                self._invalidate_track_derivatives_in_transaction(
                    connection,
                    video_id,
                    {target_track_id, source_track_id},
                )
                self._finalize_track_mutation_in_transaction(
                    connection,
                    video_id,
                    "tracks_merged",
                    pose_cache_version=pose_cache_version,
                )
                row = connection.execute(
                    "SELECT * FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, target_track_id),
                ).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._decode(row) or {}

    def merge_multiple_tracks_atomically(
        self,
        video_id: str,
        track_ids: Sequence[int],
        *,
        pose_cache_version: str | None = None,
        expected_pose_cache_version: str | None = None,
    ) -> dict[str, Any]:
        """Merge a worker selection in one transaction and emit one refresh."""

        if len(track_ids) < 2 or len(set(track_ids)) != len(track_ids):
            raise ValueError("At least two distinct track IDs are required")
        target_track_id = int(track_ids[0])
        source_track_ids = [int(track_id) for track_id in track_ids[1:]]
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._assert_expected_pose_cache_version(
                    connection,
                    video_id,
                    expected_pose_cache_version,
                )
                target = connection.execute(
                    "SELECT * FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, target_track_id),
                ).fetchone()
                if target is None:
                    raise VideoResourceNotFoundError("Track not found")
                sources = [
                    connection.execute(
                        "SELECT * FROM video_tracks WHERE video_id=? AND track_id=?",
                        (video_id, source_track_id),
                    ).fetchone()
                    for source_track_id in source_track_ids
                ]
                if any(source is None for source in sources):
                    raise VideoResourceNotFoundError("Track not found")
                valid_sources = [source for source in sources if source is not None]
                connection.execute(
                    """
                    UPDATE video_tracks
                    SET start_frame=?,
                        end_frame=?,
                        valid_frame_count=?,
                        quality_status=?,
                        revision=revision+1,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE video_id=? AND track_id=?
                    """,
                    (
                        min(
                            int(target["start_frame"]),
                            *(int(source["start_frame"]) for source in valid_sources),
                        ),
                        max(
                            int(target["end_frame"]),
                            *(int(source["end_frame"]) for source in valid_sources),
                        ),
                        int(target["valid_frame_count"])
                        + sum(
                            int(source["valid_frame_count"])
                            for source in valid_sources
                        ),
                        target["quality_status"],
                        video_id,
                        target_track_id,
                    ),
                )
                placeholders = ",".join("?" for _ in source_track_ids)
                connection.execute(
                    "UPDATE video_segments SET track_id=? "
                    f"WHERE video_id=? AND track_id IN ({placeholders})",
                    [target_track_id, video_id, *source_track_ids],
                )
                connection.execute(
                    "DELETE FROM video_tracks WHERE video_id=? "
                    f"AND track_id IN ({placeholders})",
                    [video_id, *source_track_ids],
                )
                self._invalidate_track_derivatives_in_transaction(
                    connection,
                    video_id,
                    {target_track_id, *source_track_ids},
                )
                self._finalize_track_mutation_in_transaction(
                    connection,
                    video_id,
                    "tracks_merged",
                    pose_cache_version=pose_cache_version,
                )
                row = connection.execute(
                    "SELECT * FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, target_track_id),
                ).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._decode(row) or {}

    def split_track_atomically(
        self,
        video_id: str,
        track_id: int,
        frame: int,
        *,
        new_track_id: int | None = None,
        pose_cache_version: str | None = None,
        expected_pose_cache_version: str | None = None,
    ) -> list[dict[str, Any]]:
        """Split one worker and finalize all dependent state in one commit."""

        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                self._assert_expected_pose_cache_version(
                    connection,
                    video_id,
                    expected_pose_cache_version,
                )
                track = connection.execute(
                    "SELECT * FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, track_id),
                ).fetchone()
                if track is None:
                    raise VideoResourceNotFoundError("Track not found")
                if not int(track["start_frame"]) < frame <= int(track["end_frame"]):
                    raise ValueError("Track split frame must be inside its lifespan")
                if new_track_id is None:
                    highest = connection.execute(
                        "SELECT COALESCE(MAX(track_id), 0) AS value "
                        "FROM video_tracks WHERE video_id=?",
                        (video_id,),
                    ).fetchone()
                    new_track_id = int(highest["value"]) + 1
                elif connection.execute(
                    "SELECT 1 FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, new_track_id),
                ).fetchone() is not None:
                    raise ValueError("A concurrent track edit changed the split target")
                fields = {
                    "track_id": new_track_id,
                    "start_frame": frame,
                    "end_frame": int(track["end_frame"]),
                    "valid_frame_count": int(track["valid_frame_count"]),
                    "gap_count": int(track["gap_count"]),
                    "avg_person_confidence": float(track["avg_person_confidence"]),
                    "avg_keypoint_confidence": float(track["avg_keypoint_confidence"]),
                    "valid_frame_ratio": float(track["valid_frame_ratio"]),
                    "missing_ankle_ratio": float(track["missing_ankle_ratio"]),
                    "quality_status": str(track["quality_status"]),
                    "include_in_export": int(track["include_in_export"]),
                    "exclude_reason": track["exclude_reason"],
                }
                names = ["track_pk", "video_id", *fields.keys()]
                connection.execute(
                    f"INSERT INTO video_tracks({','.join(names)}) "
                    f"VALUES ({','.join('?' for _ in names)})",
                    [uuid4().hex, video_id, *fields.values()],
                )
                connection.execute(
                    """
                    UPDATE video_tracks
                    SET end_frame=?, revision=revision+1, updated_at=CURRENT_TIMESTAMP
                    WHERE video_id=? AND track_id=?
                    """,
                    (frame - 1, video_id, track_id),
                )
                connection.execute(
                    """
                    UPDATE video_segments
                    SET track_id=?
                    WHERE video_id=? AND track_id=? AND start_frame>=?
                    """,
                    (new_track_id, video_id, track_id, frame),
                )
                self._invalidate_track_derivatives_in_transaction(
                    connection,
                    video_id,
                    {track_id, new_track_id},
                )
                self._finalize_track_mutation_in_transaction(
                    connection,
                    video_id,
                    "track_split",
                    pose_cache_version=pose_cache_version,
                )
                rows = connection.execute(
                    "SELECT * FROM video_tracks WHERE video_id=? AND track_id IN (?, ?) "
                    "ORDER BY track_id",
                    (video_id, track_id, new_track_id),
                ).fetchall()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return [self._decode(row) or {} for row in rows]

    def set_track_inclusion_atomically(
        self,
        video_id: str,
        track_id: int,
        include: bool,
        reason: str | None,
    ) -> dict[str, Any]:
        """Change worker export inclusion with its revision and events together."""

        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    "SELECT * FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, track_id),
                ).fetchone()
                if existing is None:
                    raise VideoResourceNotFoundError("Track not found")
                connection.execute(
                    """
                    UPDATE video_tracks
                    SET include_in_export=?,
                        exclude_reason=?,
                        quality_status=?,
                        revision=revision+1,
                        updated_at=CURRENT_TIMESTAMP
                    WHERE video_id=? AND track_id=?
                    """,
                    (
                        int(include),
                        None if include else reason,
                        "good" if include else "excluded",
                        video_id,
                        track_id,
                    ),
                )
                self._invalidate_track_derivatives_in_transaction(
                    connection,
                    video_id,
                    {track_id},
                )
                self._finalize_track_mutation_in_transaction(
                    connection,
                    video_id,
                    "track_inclusion_changed",
                )
                row = connection.execute(
                    "SELECT * FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, track_id),
                ).fetchone()
                connection.commit()
            except Exception:
                connection.rollback()
                raise
        return self._decode(row) or {}

    def delete_track_atomically(self, video_id: str, track_id: int) -> None:
        """Delete a worker and its labels with all invalidation state atomically."""

        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                existing = connection.execute(
                    "SELECT 1 FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, track_id),
                ).fetchone()
                if existing is None:
                    raise VideoResourceNotFoundError("Track not found")
                connection.execute(
                    "DELETE FROM video_segments WHERE video_id=? AND track_id=?",
                    (video_id, track_id),
                )
                connection.execute(
                    "DELETE FROM video_tracks WHERE video_id=? AND track_id=?",
                    (video_id, track_id),
                )
                self._invalidate_track_derivatives_in_transaction(
                    connection,
                    video_id,
                    {track_id},
                )
                self._finalize_track_mutation_in_transaction(
                    connection,
                    video_id,
                    "track_deleted",
                )
                connection.commit()
            except Exception:
                connection.rollback()
                raise

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
        *,
        emit_event: bool = True,
        schedule_derivatives: bool = True,
    ) -> tuple[dict[str, Any], int]:
        with self.connection() as connection, connection:
            video = connection.execute(
                "SELECT annotation_revision FROM videos WHERE video_id=?", (video_id,)
            ).fetchone()
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
            if emit_event:
                self._emit_annotation_changed(connection, video_id, f"segment_{operation}")
            if schedule_derivatives:
                self._schedule_annotation_derivatives_if_ready(
                    connection,
                    video_id,
                    revision,
                )
        return new, revision

    def materialize_suggestion_segments(
        self,
        video_id: str,
        suggestion_table: str,
        selected_suggestion_ids: Sequence[str],
        segments: Sequence[dict[str, Any]],
        *,
        expected_revision: int | None = None,
    ) -> list[dict[str, Any]]:
        """Atomically turn one suggestion set into editable ground truth.

        The worker must never partially write automatic labels if a manual edit
        interleaves. An immediate SQLite transaction rechecks the pinned
        revision and blank annotation state, writes every segment/history row,
        accepts its source suggestions, bumps the revision, and emits one
        annotation event as one durable unit.
        """

        if suggestion_table not in {"threshold_suggestions", "model_suggestions"}:
            raise ValueError("Unsupported suggestion table")
        suggestion_ids = list(dict.fromkeys(str(item) for item in selected_suggestion_ids))
        with self.connection() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                video_row = connection.execute(
                    "SELECT annotation_revision FROM videos WHERE video_id=?",
                    (video_id,),
                ).fetchone()
                if video_row is None:
                    raise VideoResourceNotFoundError("Video not found")
                current_revision = int(video_row["annotation_revision"])
                if (
                    expected_revision is not None
                    and current_revision != expected_revision
                ):
                    connection.commit()
                    return []
                has_segments = connection.execute(
                    "SELECT 1 FROM video_segments WHERE video_id=? LIMIT 1",
                    (video_id,),
                ).fetchone()
                if has_segments is not None:
                    connection.commit()
                    return []
                if suggestion_ids:
                    placeholders = ",".join("?" for _ in suggestion_ids)
                    pending_rows = connection.execute(
                        f"""
                        SELECT suggestion_id FROM {suggestion_table}
                        WHERE video_id=?
                          AND review_status='pending'
                          AND suggestion_id IN ({placeholders})
                        """,
                        [video_id, *suggestion_ids],
                    ).fetchall()
                    if {str(row["suggestion_id"]) for row in pending_rows} != set(
                        suggestion_ids
                    ):
                        connection.commit()
                        return []

                created: list[dict[str, Any]] = []
                revision = current_revision
                for segment in segments:
                    revision += 1
                    segment_id = uuid4().hex
                    fields = {
                        "track_id": int(segment["track_id"]),
                        "start_frame": int(segment["start_frame"]),
                        "end_frame": int(segment["end_frame"]),
                        "label": str(segment["label"]),
                        "quality_status": str(segment.get("quality_status", "good")),
                        "include_in_export": int(segment.get("include_in_export", 1)),
                        "exclude_reason": segment.get("exclude_reason"),
                        "annotation_version": revision,
                        "source_type": str(segment["source_type"]),
                        "source_id": segment.get("source_id"),
                    }
                    names = ["segment_id", "video_id", *fields.keys()]
                    connection.execute(
                        f"INSERT INTO video_segments({','.join(names)}) "
                        f"VALUES ({','.join('?' for _ in names)})",
                        [segment_id, video_id, *fields.values()],
                    )
                    row = connection.execute(
                        "SELECT * FROM video_segments WHERE segment_id=?",
                        (segment_id,),
                    ).fetchone()
                    created_segment = dict(row)
                    self._record_history(
                        connection,
                        video_id,
                        segment_id,
                        "create",
                        None,
                        created_segment,
                        revision,
                    )
                    created.append(created_segment)

                if not created:
                    connection.commit()
                    return []
                if suggestion_ids:
                    placeholders = ",".join("?" for _ in suggestion_ids)
                    connection.execute(
                        f"""
                        UPDATE {suggestion_table}
                        SET review_status='accepted', updated_at=CURRENT_TIMESTAMP
                        WHERE video_id=? AND suggestion_id IN ({placeholders})
                        """,
                        [video_id, *suggestion_ids],
                    )
                self._bump_annotation_revision(connection, video_id, revision)
                self._emit_annotation_changed(
                    connection,
                    video_id,
                    "suggestions_materialized",
                )
                # The final suggestion stage may crash after this committed
                # ground-truth write. Persist the derivative intent before
                # returning so recovery can enqueue a fresh, revision-pinned
                # windows/features job without relying on an in-process call.
                self._schedule_annotation_derivatives_if_ready(
                    connection,
                    video_id,
                    revision,
                )
                connection.commit()
                return created
            except Exception:
                connection.rollback()
                raise

    def delete_segment(
        self,
        video_id: str,
        segment_id: str,
        expected_revision: int,
        *,
        schedule_derivatives: bool = True,
    ) -> int:
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
            remaining = connection.execute(
                "SELECT 1 FROM video_segments WHERE video_id=? LIMIT 1", (video_id,)
            ).fetchone()
            self._bump_annotation_revision(
                connection,
                video_id,
                revision,
                annotation_status="labeled" if remaining is not None else "unlabeled",
            )
            self._emit_annotation_changed(connection, video_id, "segment_delete")
            if schedule_derivatives:
                self._schedule_annotation_derivatives_if_ready(
                    connection,
                    video_id,
                    revision,
                )
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
    def _bump_annotation_revision(
        connection: sqlite3.Connection,
        video_id: str,
        revision: int,
        *,
        annotation_status: str = "labeled",
    ) -> None:
        connection.execute(
            "UPDATE videos SET annotation_revision=?,is_approved=0,approval_revision=NULL,approved_at=NULL,annotation_status=?,feature_cache_version=NULL,window_cache_version=NULL,updated_at=CURRENT_TIMESTAMP WHERE video_id=?",
            (revision, annotation_status, video_id),
        )
        connection.execute("UPDATE generated_windows SET stale=1 WHERE video_id=?", (video_id,))

    def list_history(self, video_id: str) -> list[dict[str, Any]]:
        return self.all("SELECT * FROM annotation_history WHERE video_id=? ORDER BY revision DESC", (video_id,))

    def undo_or_redo(
        self,
        video_id: str,
        expected_revision: int,
        mode: str,
        *,
        schedule_derivatives: bool = True,
    ) -> int:
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
            remaining = connection.execute(
                "SELECT 1 FROM video_segments WHERE video_id=? LIMIT 1", (video_id,)
            ).fetchone()
            self._bump_annotation_revision(
                connection,
                video_id,
                revision,
                annotation_status="labeled" if remaining is not None else "unlabeled",
            )
            self._emit_annotation_changed(connection, video_id, f"history_{mode}")
            if schedule_derivatives:
                self._schedule_annotation_derivatives_if_ready(
                    connection,
                    video_id,
                    revision,
                )
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
        with self.connection() as connection, connection:
            connection.execute(
                "INSERT INTO video_exports(export_id,project_id) VALUES (?,?)",
                (export_id, project_id),
            )
            row = connection.execute(
                "SELECT * FROM video_exports WHERE export_id=?", (export_id,)
            ).fetchone()
            export = self._decode(row) or {}
            self._emit_workspace_event(
                connection,
                project_id,
                "export.changed",
                self._export_event_payload(export),
            )
        return export

    def update_export(self, export_id: str, **values: Any) -> dict[str, Any]:
        """Update one export and publish its compact state atomically."""

        if not values:
            return self.get_export(export_id)
        assignments = ",".join(f"{key}=?" for key in values)
        with self.connection() as connection, connection:
            existing = connection.execute(
                "SELECT * FROM video_exports WHERE export_id=?", (export_id,)
            ).fetchone()
            if existing is None:
                raise VideoResourceNotFoundError("Export not found")
            connection.execute(
                f"UPDATE video_exports SET {assignments} WHERE export_id=?",
                [*values.values(), export_id],
            )
            row = connection.execute(
                "SELECT * FROM video_exports WHERE export_id=?", (export_id,)
            ).fetchone()
            export = self._decode(row) or {}
            self._emit_workspace_event(
                connection,
                str(export["project_id"]),
                "export.changed",
                self._export_event_payload(export),
            )
        return export

    def get_export(self, export_id: str) -> dict[str, Any]:
        export = self.one("SELECT * FROM video_exports WHERE export_id=?", (export_id,))
        if export is None:
            raise VideoResourceNotFoundError("Export not found")
        return export

    def list_exports(self, project_id: str) -> list[dict[str, Any]]:
        return self.all("SELECT * FROM video_exports WHERE project_id=? ORDER BY created_at DESC", (project_id,))
