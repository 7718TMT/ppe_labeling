# Database and storage reference

<!-- BEGIN GENERATED NOTICE -->
> **Generated file — do not edit by hand.**
> Produced by `backend/scripts/generate_docs.py` from `backend/app/repositories/approvals.py`, `backend/app/repositories/video_db.py`.
> Regenerate after changing those sources; edit the generator scripts, not this file.
> Run `uv run python -m backend.scripts.generate_docs`.
>
> Generated 2026-10-30 at commit `4d2ea6fc58f9`.
> Commit identifies the checkout; output may include uncommitted source changes.
<!-- END GENERATED NOTICE -->

SQLite stores image approval state plus video projects, jobs, annotation history,
tracks, windows, model metadata and exports. Image inventory and YOLO text labels
are filesystem data, not database rows. Video media, pose/features and export
payloads also remain on disk. Keep the configured database and storage roots
together when backing up; an export alone cannot restore a workspace.

Image approval stores current state only, with no approval audit history. Video
annotation history is separate. Migrations run when the video repository opens.
The schema below is produced by applying those migrations to a temporary empty
database, never by inspecting your live installation. NOT NULL shows the SQLite
PRAGMA flag; consult table constraints for primary-key semantics.

See [operations](OPERATIONS.md) for backup and migration instructions.
Regenerate with `uv run python -m backend.scripts.generate_docs`.

<!-- BEGIN GENERATED -->
Video schema version: **4**.

## `annotation_derivative_refreshes`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| video_id | TEXT | False | None | 1 |
| project_id | TEXT | True | None | 0 |
| requested_revision | INTEGER | True | None | 0 |
| requested_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE annotation_derivative_refreshes (
                video_id TEXT PRIMARY KEY REFERENCES videos(video_id)
                    ON DELETE CASCADE,
                project_id TEXT NOT NULL REFERENCES video_projects(project_id)
                    ON DELETE CASCADE,
                requested_revision INTEGER NOT NULL,
                requested_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
```

Indexes:

- `idx_derivative_refreshes_project`: columns `['project_id', 'requested_at']`, unique=False, origin=c, partial=False

```sql
CREATE INDEX idx_derivative_refreshes_project
                ON annotation_derivative_refreshes(project_id, requested_at);
```

- `sqlite_autoindex_annotation_derivative_refreshes_1`: columns `['video_id']`, unique=True, origin=pk, partial=False

## `annotation_history`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| history_id | TEXT | False | None | 1 |
| video_id | TEXT | True | None | 0 |
| entity_type | TEXT | True | None | 0 |
| entity_id | TEXT | True | None | 0 |
| operation | TEXT | True | None | 0 |
| old_value_json | TEXT | False | None | 0 |
| new_value_json | TEXT | False | None | 0 |
| revision | INTEGER | True | None | 0 |
| user_id | TEXT | True | 'local-user' | 0 |
| undone | INTEGER | True | 0 | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE annotation_history (
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
```

Indexes:

- `idx_history_video`: columns `['video_id', 'revision']`, unique=False, origin=c, partial=False

```sql
CREATE INDEX idx_history_video ON annotation_history(video_id, revision DESC);
```

- `sqlite_autoindex_annotation_history_1`: columns `['history_id']`, unique=True, origin=pk, partial=False

## `approval_status`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| task_id | TEXT | True | None | 1 |
| filename | TEXT | True | None | 2 |
| is_approved | INTEGER | True | None | 0 |
| updated_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE approval_status (
    task_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    is_approved INTEGER NOT NULL CHECK (is_approved IN (0, 1)),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, filename)
);
```

Indexes:

- `sqlite_autoindex_approval_status_1`: columns `['task_id', 'filename']`, unique=True, origin=pk, partial=False

## `canonical_frame_mappings`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| video_id | TEXT | True | None | 1 |
| canonical_frame | INTEGER | True | None | 2 |
| original_frame | INTEGER | True | None | 0 |
| timestamp_seconds | REAL | True | None | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE canonical_frame_mappings (
    video_id TEXT NOT NULL REFERENCES videos(video_id) ON DELETE CASCADE,
    canonical_frame INTEGER NOT NULL,
    original_frame INTEGER NOT NULL,
    timestamp_seconds REAL NOT NULL,
    PRIMARY KEY(video_id, canonical_frame)
);
```

Indexes:

- `sqlite_autoindex_canonical_frame_mappings_1`: columns `['video_id', 'canonical_frame']`, unique=True, origin=pk, partial=False

## `external_models`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| external_model_id | TEXT | False | None | 1 |
| project_id | TEXT | True | None | 0 |
| name | TEXT | True | None | 0 |
| version | TEXT | True | None | 0 |
| artifact_path | TEXT | True | None | 0 |
| artifact_hash | TEXT | True | None | 0 |
| adapter_type | TEXT | True | None | 0 |
| class_map_json | TEXT | True | None | 0 |
| feature_schema_version | TEXT | True | None | 0 |
| feature_columns_json | TEXT | True | None | 0 |
| window_config_json | TEXT | True | None | 0 |
| compatibility_status | TEXT | True | None | 0 |
| compatibility_errors_json | TEXT | True | '[]' | 0 |
| metadata_json | TEXT | True | None | 0 |
| is_active | INTEGER | True | 0 | 0 |
| loaded_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE external_models (
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
```

Indexes:

- `sqlite_autoindex_external_models_1`: columns `['external_model_id']`, unique=True, origin=pk, partial=False
- `sqlite_autoindex_external_models_2`: columns `['project_id', 'name', 'version', 'artifact_hash']`, unique=True, origin=u, partial=False
- `uq_external_models_active_project`: columns `['project_id']`, unique=True, origin=c, partial=True

```sql
CREATE UNIQUE INDEX uq_external_models_active_project
            ON external_models(project_id)
            WHERE is_active=1
            ;
```


## `generated_windows`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| window_id | TEXT | False | None | 1 |
| video_id | TEXT | True | None | 0 |
| track_id | INTEGER | True | None | 0 |
| start_frame | INTEGER | True | None | 0 |
| end_frame | INTEGER | True | None | 0 |
| label | TEXT | False | None | 0 |
| label_reason | TEXT | False | None | 0 |
| quality_score | REAL | True | 0 | 0 |
| quality_status | TEXT | True | 'unlabeled' | 0 |
| include_in_export | INTEGER | True | 0 | 0 |
| exclude_reason | TEXT | False | None | 0 |
| window_config_version | TEXT | True | None | 0 |
| feature_status | TEXT | True | 'pending' | 0 |
| stale | INTEGER | True | 0 | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |
| updated_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE generated_windows (
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
```

Indexes:

- `idx_windows_video_track`: columns `['video_id', 'track_id', 'start_frame']`, unique=False, origin=c, partial=False

```sql
CREATE INDEX idx_windows_video_track
    ON generated_windows(video_id, track_id, start_frame);
```

- `sqlite_autoindex_generated_windows_1`: columns `['window_id']`, unique=True, origin=pk, partial=False
- `sqlite_autoindex_generated_windows_2`: columns `['video_id', 'track_id', 'start_frame', 'window_config_version']`, unique=True, origin=u, partial=False

## `model_suggestions`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| suggestion_id | TEXT | False | None | 1 |
| external_model_id | TEXT | True | None | 0 |
| video_id | TEXT | True | None | 0 |
| track_id | INTEGER | True | None | 0 |
| start_frame | INTEGER | True | None | 0 |
| end_frame | INTEGER | True | None | 0 |
| suggested_label | TEXT | True | None | 0 |
| confidence | REAL | True | None | 0 |
| source_window_ids_json | TEXT | True | None | 0 |
| probabilities_json | TEXT | True | None | 0 |
| merge_config_json | TEXT | True | None | 0 |
| review_status | TEXT | True | 'pending' | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |
| updated_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE model_suggestions (
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
```

Indexes:

- `idx_model_suggestions_video`: columns `['video_id', 'track_id', 'review_status']`, unique=False, origin=c, partial=False

```sql
CREATE INDEX idx_model_suggestions_video
    ON model_suggestions(video_id, track_id, review_status);
```

- `sqlite_autoindex_model_suggestions_1`: columns `['suggestion_id']`, unique=True, origin=pk, partial=False

## `model_window_predictions`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| prediction_id | TEXT | False | None | 1 |
| external_model_id | TEXT | True | None | 0 |
| window_id | TEXT | True | None | 0 |
| others_probability | REAL | True | None | 0 |
| running_probability | REAL | True | None | 0 |
| falling_probability | REAL | True | None | 0 |
| predicted_label | TEXT | True | None | 0 |
| confidence | REAL | True | None | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE model_window_predictions (
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
```

Indexes:

- `sqlite_autoindex_model_window_predictions_1`: columns `['prediction_id']`, unique=True, origin=pk, partial=False
- `sqlite_autoindex_model_window_predictions_2`: columns `['external_model_id', 'window_id']`, unique=True, origin=u, partial=False

## `processing_jobs`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| job_id | TEXT | False | None | 1 |
| project_id | TEXT | True | None | 0 |
| video_id | TEXT | False | None | 0 |
| stage | TEXT | True | None | 0 |
| status | TEXT | True | 'queued' | 0 |
| priority | INTEGER | True | 100 | 0 |
| progress | REAL | True | 0 | 0 |
| error_message | TEXT | False | None | 0 |
| log_json | TEXT | True | '[]' | 0 |
| control_requested | TEXT | False | None | 0 |
| worker_id | TEXT | False | None | 0 |
| retry_count | INTEGER | True | 0 | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |
| started_at | TEXT | False | None | 0 |
| heartbeat_at | TEXT | False | None | 0 |
| finished_at | TEXT | False | None | 0 |
| updated_at | TEXT | True | CURRENT_TIMESTAMP | 0 |
| target_mode | TEXT | True | 'threshold' | 0 |
| external_model_id | TEXT | False | None | 0 |
| annotation_revision | INTEGER | False | None | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE processing_jobs (
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
, target_mode TEXT NOT NULL DEFAULT 'threshold'
                    CHECK(target_mode IN ('threshold', 'model')), external_model_id TEXT
                    REFERENCES external_models(external_model_id), annotation_revision INTEGER);
```

Indexes:

- `idx_jobs_claim`: columns `['status', 'priority', 'created_at']`, unique=False, origin=c, partial=False

```sql
CREATE INDEX idx_jobs_claim
    ON processing_jobs(status, priority DESC, created_at);
```

- `idx_jobs_video`: columns `['video_id', 'stage', 'status']`, unique=False, origin=c, partial=False

```sql
CREATE INDEX idx_jobs_video ON processing_jobs(video_id, stage, status);
```

- `sqlite_autoindex_processing_jobs_1`: columns `['job_id']`, unique=True, origin=pk, partial=False
- `uq_processing_jobs_active_video`: columns `['video_id']`, unique=True, origin=c, partial=True

```sql
CREATE UNIQUE INDEX uq_processing_jobs_active_video
            ON processing_jobs(video_id)
            WHERE video_id IS NOT NULL
              AND status IN ('queued', 'running', 'paused')
            ;
```


## `threshold_profiles`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| threshold_profile_id | TEXT | False | None | 1 |
| project_id | TEXT | True | None | 0 |
| name | TEXT | True | None | 0 |
| version | TEXT | True | None | 0 |
| config_json | TEXT | True | None | 0 |
| is_default | INTEGER | True | 0 | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |
| updated_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE threshold_profiles (
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
```

Indexes:

- `sqlite_autoindex_threshold_profiles_1`: columns `['threshold_profile_id']`, unique=True, origin=pk, partial=False
- `sqlite_autoindex_threshold_profiles_2`: columns `['project_id', 'name', 'version']`, unique=True, origin=u, partial=False

## `threshold_suggestions`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| suggestion_id | TEXT | False | None | 1 |
| threshold_profile_id | TEXT | True | None | 0 |
| video_id | TEXT | True | None | 0 |
| track_id | INTEGER | True | None | 0 |
| start_frame | INTEGER | True | None | 0 |
| end_frame | INTEGER | True | None | 0 |
| suggested_label | TEXT | True | None | 0 |
| confidence | REAL | True | None | 0 |
| triggered_conditions_json | TEXT | True | None | 0 |
| supporting_features_json | TEXT | True | None | 0 |
| quality_status | TEXT | True | None | 0 |
| review_status | TEXT | True | 'pending' | 0 |
| artifact_key | TEXT | True | None | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |
| updated_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE threshold_suggestions (
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
```

Indexes:

- `idx_threshold_suggestions_video`: columns `['video_id', 'track_id', 'review_status']`, unique=False, origin=c, partial=False

```sql
CREATE INDEX idx_threshold_suggestions_video
    ON threshold_suggestions(video_id, track_id, review_status);
```

- `sqlite_autoindex_threshold_suggestions_1`: columns `['suggestion_id']`, unique=True, origin=pk, partial=False
- `sqlite_autoindex_threshold_suggestions_2`: columns `['threshold_profile_id', 'video_id', 'track_id', 'artifact_key']`, unique=True, origin=u, partial=False

## `video_exports`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| export_id | TEXT | False | None | 1 |
| project_id | TEXT | True | None | 0 |
| job_id | TEXT | False | None | 0 |
| status | TEXT | True | 'queued' | 0 |
| artifact_path | TEXT | False | None | 0 |
| manifest_json | TEXT | False | None | 0 |
| validation_json | TEXT | True | '[]' | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |
| finished_at | TEXT | False | None | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE video_exports (
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
```

Indexes:

- `sqlite_autoindex_video_exports_1`: columns `['export_id']`, unique=True, origin=pk, partial=False

## `video_projects`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| project_id | TEXT | False | None | 1 |
| name | TEXT | True | None | 0 |
| config_json | TEXT | True | None | 0 |
| application_version | TEXT | True | None | 0 |
| active_threshold_profile_id | TEXT | False | None | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |
| updated_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE video_projects (
    project_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    config_json TEXT NOT NULL,
    application_version TEXT NOT NULL,
    active_threshold_profile_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Indexes:

- `sqlite_autoindex_video_projects_1`: columns `['project_id']`, unique=True, origin=pk, partial=False

## `video_schema_migrations`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| version | INTEGER | False | None | 1 |
| applied_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE video_schema_migrations (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Indexes:


## `video_segments`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| segment_id | TEXT | False | None | 1 |
| video_id | TEXT | True | None | 0 |
| track_id | INTEGER | True | None | 0 |
| start_frame | INTEGER | True | None | 0 |
| end_frame | INTEGER | True | None | 0 |
| label | TEXT | True | None | 0 |
| quality_status | TEXT | True | 'good' | 0 |
| include_in_export | INTEGER | True | 1 | 0 |
| exclude_reason | TEXT | False | None | 0 |
| annotation_version | INTEGER | True | None | 0 |
| source_type | TEXT | True | 'manual' | 0 |
| source_id | TEXT | False | None | 0 |
| created_by | TEXT | True | 'local-user' | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |
| updated_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE video_segments (
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
```

Indexes:

- `idx_segments_track`: columns `['video_id', 'track_id', 'start_frame', 'end_frame']`, unique=False, origin=c, partial=False

```sql
CREATE INDEX idx_segments_track
    ON video_segments(video_id, track_id, start_frame, end_frame);
```

- `sqlite_autoindex_video_segments_1`: columns `['segment_id']`, unique=True, origin=pk, partial=False

## `video_tracks`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| track_pk | TEXT | False | None | 1 |
| video_id | TEXT | True | None | 0 |
| track_id | INTEGER | True | None | 0 |
| start_frame | INTEGER | True | None | 0 |
| end_frame | INTEGER | True | None | 0 |
| valid_frame_count | INTEGER | True | 0 | 0 |
| gap_count | INTEGER | True | 0 | 0 |
| avg_person_confidence | REAL | True | 0 | 0 |
| avg_keypoint_confidence | REAL | True | 0 | 0 |
| valid_frame_ratio | REAL | True | 0 | 0 |
| missing_ankle_ratio | REAL | True | 1 | 0 |
| quality_status | TEXT | True | 'unknown' | 0 |
| include_in_export | INTEGER | True | 1 | 0 |
| exclude_reason | TEXT | False | None | 0 |
| revision | INTEGER | True | 1 | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |
| updated_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE video_tracks (
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
```

Indexes:

- `idx_tracks_video`: columns `['video_id', 'track_id']`, unique=False, origin=c, partial=False

```sql
CREATE INDEX idx_tracks_video ON video_tracks(video_id, track_id);
```

- `sqlite_autoindex_video_tracks_1`: columns `['track_pk']`, unique=True, origin=pk, partial=False
- `sqlite_autoindex_video_tracks_2`: columns `['video_id', 'track_id']`, unique=True, origin=u, partial=False

## `video_workspace_events`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| event_id | INTEGER | False | None | 1 |
| project_id | TEXT | True | None | 0 |
| video_id | TEXT | False | None | 0 |
| event_type | TEXT | True | None | 0 |
| payload_json | TEXT | True | None | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE video_workspace_events (
                event_id INTEGER PRIMARY KEY AUTOINCREMENT,
                project_id TEXT NOT NULL REFERENCES video_projects(project_id)
                    ON DELETE CASCADE,
                video_id TEXT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
```

Indexes:

- `idx_workspace_events_project_event`: columns `['project_id', 'event_id']`, unique=False, origin=c, partial=False

```sql
CREATE INDEX idx_workspace_events_project_event
                ON video_workspace_events(project_id, event_id);
```


## `video_workspace_state`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| project_id | TEXT | False | None | 1 |
| video_id | TEXT | False | None | 0 |
| track_id | INTEGER | False | None | 0 |
| frame_index | INTEGER | True | 0 | 0 |
| suggestion_source | TEXT | True | 'Threshold' | 0 |
| updated_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE video_workspace_state (
    project_id TEXT PRIMARY KEY REFERENCES video_projects(project_id) ON DELETE CASCADE,
    video_id TEXT,
    track_id INTEGER,
    frame_index INTEGER NOT NULL DEFAULT 0,
    suggestion_source TEXT NOT NULL DEFAULT 'Threshold',
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
```

Indexes:

- `sqlite_autoindex_video_workspace_state_1`: columns `['project_id']`, unique=True, origin=pk, partial=False

## `videos`

| Column | Type | NOT NULL | Default | PK position |
|---|---|---|---|---|
| video_id | TEXT | False | None | 1 |
| project_id | TEXT | True | None | 0 |
| filename | TEXT | True | None | 0 |
| relative_path | TEXT | True | None | 0 |
| file_hash | TEXT | True | None | 0 |
| original_fps | REAL | True | None | 0 |
| canonical_fps | REAL | True | 24 | 0 |
| original_frame_count | INTEGER | True | None | 0 |
| canonical_frame_count | INTEGER | True | None | 0 |
| duration_seconds | REAL | True | None | 0 |
| width | INTEGER | True | None | 0 |
| height | INTEGER | True | None | 0 |
| codec | TEXT | False | None | 0 |
| file_size | INTEGER | True | None | 0 |
| folder_group | TEXT | False | None | 0 |
| processing_status | TEXT | True | 'imported' | 0 |
| annotation_status | TEXT | True | 'unlabeled' | 0 |
| quality_status | TEXT | True | 'unknown' | 0 |
| include_in_export | INTEGER | True | 1 | 0 |
| exclude_reason | TEXT | False | None | 0 |
| annotation_revision | INTEGER | True | 0 | 0 |
| is_approved | INTEGER | True | 0 | 0 |
| approval_revision | INTEGER | False | None | 0 |
| approved_at | TEXT | False | None | 0 |
| pose_cache_version | TEXT | False | None | 0 |
| tracking_cache_version | TEXT | False | None | 0 |
| feature_cache_version | TEXT | False | None | 0 |
| threshold_cache_version | TEXT | False | None | 0 |
| window_cache_version | TEXT | False | None | 0 |
| last_error | TEXT | False | None | 0 |
| created_at | TEXT | True | CURRENT_TIMESTAMP | 0 |
| updated_at | TEXT | True | CURRENT_TIMESTAMP | 0 |

Table constraints and foreign keys:

```sql
CREATE TABLE videos (
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
```

Indexes:

- `idx_videos_project_status`: columns `['project_id', 'processing_status', 'annotation_status']`, unique=False, origin=c, partial=False

```sql
CREATE INDEX idx_videos_project_status
    ON videos(project_id, processing_status, annotation_status);
```

- `sqlite_autoindex_videos_1`: columns `['video_id']`, unique=True, origin=pk, partial=False
- `sqlite_autoindex_videos_2`: columns `['project_id', 'file_hash']`, unique=True, origin=u, partial=False
<!-- END GENERATED -->
