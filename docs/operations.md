# Operations Guide

## Configuration and local execution

Copy `.env.example` to `.env` and run commands from the repository root. Paths
in `DATABASE_PATH` and task-profile settings are relative to that working
directory unless absolute paths are supplied.

Start the complete local product with one command:

```powershell
uv run python -m backend.scripts.start_app
```

The launcher starts FastAPI, the persistent video worker, and Vite, and stops
all three on `Ctrl+C`. Ports `8000` and `5173` must be available.

`CORS_ORIGINS` controls FastAPI CORS. During local frontend development, Vite
proxies `/api/v1` and `/media` to `VITE_BACKEND_URL` (default
`http://localhost:8000`). Production deployments must provide an equivalent
reverse-proxy route or configure the frontend to reach the backend correctly.

## Filesystem data contract

Each configured task has three independent directories:

```text
images/          source image files; this is the visible image inventory
labels/          YOLO text labels with matching image basenames
labeled_images/  generated verified_*.jpg visualizations
```

Manual ingestion remains supported: copy a `.jpg`, `.jpeg`, or `.png` file into
the task's `images/` directory, then refresh the UI. The API upload workflow
uses the same directory. Images, labels, and visualizations are dataset
artifacts and are never copied into SQLite.

Do not manually place two images with the same stem (for example `sample.jpg`
and `sample.png`) in one task. YOLO labels and visualizations use the stem as
their key. API uploads automatically add a numeric suffix to avoid this; manual
collisions are shown in the image inventory but mutable/export workflows reject
them with a conflict until one file is renamed manually.

## SQLite approval metadata

`DATABASE_PATH` points to SQLite current-state metadata. The repository enables
WAL mode and a five-second busy timeout. Back up SQLite with SQLite's backup
facility or after stopping the application; copying only the main database file
while its `-wal` file is active may omit recent transactions.

Approval is intentionally current state only. Approve writes or updates a row;
unapprove deletes it. An approval can only be created for an image that exists
on disk; unapproving a missing image remains an idempotent stale-metadata
cleanup. No audit history is retained.

### Release migration from legacy `approved.json`

The base implementation stored approvals in each task's
`labels/approved.json`. The application never imports that file during startup.
Run this explicit release command before switching an existing deployment to
SQLite:

```powershell
# 1. Inspect every configured task. This does not write SQLite.
uv run python -m backend.scripts.migrate_legacy_approvals --all

# 2. Resolve every reported missing image, malformed entry, or failure.
# 3. Import valid approvals only after the dry-run report is clean.
uv run python -m backend.scripts.migrate_legacy_approvals --all --apply

# A single task can be migrated independently.
uv run python -m backend.scripts.migrate_legacy_approvals --task ppe --apply
```

The command reports approvals discovered, imported, already present, skipped,
missing images, malformed entries, and migration failures. It is idempotent and
does not modify or delete the source JSON. Verify the apply report shows the
expected imported or already-present count, then check the task image list in
the UI. For rollback, stop the application and restore the SQLite backup taken
before `--apply`; the original JSON remains available for a corrected rerun.

## Missing-image API contract

The task-scoped API distinguishes read/no-op behavior from writes:

- `GET .../images/{filename}/labels` returns the established empty-label
  response for a missing image and creates no file.
- `DELETE .../images/{filename}` remains successful and idempotent for a
  missing image; it removes any stale approval row but does not touch matching
  artifacts for another same-stem image.
- `PUT .../images/{filename}/labels` returns `404` for a missing image. This is
  an intentional safety rule that prevents orphan YOLO label files.

## Destructive workflow behavior

### Delete

The service deletes an image and its matching label/visualization artifacts,
then removes the approval row. Filesystem inventory remains authoritative for
the UI. If SQLite cleanup fails after file deletion, the API reports a partial
operation and the stale approval row can be reconciled.

### Sequential rename

Rename first builds the complete filename map and checks image, label, and
visualization collisions before moving files. It then renames filesystem
artifacts and remaps approvals in one SQLite transaction. Approval rows that do
not correspond to a source image are removed inside that transaction so stale
metadata cannot collide with a target filename.

Unexpected filesystem errors can still leave `.renaming` files or a partially
renamed dataset. The application reports this as a partial operation and
refuses a later sequential-rename attempt while those artifacts exist; it does
not attempt automatic rollback. Inspect and resolve the task directories before
retrying.

### Partial-operation response

For a destructive operation that has made partial progress, the response is a
500 with this shape:

```json
{
  "detail": "...",
  "reconciliation_required": true,
  "operation": {
    "filesystem_completed": true,
    "approvals_remapped": false,
    "warnings": ["..."]
  }
}
```

The success-path API schemas and task-scoped URLs are unchanged.

## Approval reconciliation

Inspect stale approval rows without changing data:

```powershell
uv run python -m backend.scripts.reconcile_approvals --task ppe
```

Remove only the rows reported as stale:

```powershell
uv run python -m backend.scripts.reconcile_approvals --task ppe --apply
```

Run the command once per configured task (`ppe` and `safety_signs`). It is safe
to repeat: a subsequent run reports no stale rows once they have been removed.

## Inference and logging

`INFERENCE_DEVICE=auto` selects `cuda:0` when PyTorch can use CUDA and CPU
otherwise. Set it to `cpu`, `cuda`, `cuda:0`, or a numeric CUDA index to make a
specific choice. Detector models load lazily when an auto-label action first
needs them. Application logs include named events and contextual fields for
model loading, device fallback, destructive operations, approval persistence
failures, exports, and reconciliation. Configure the process log handler in the
deployment environment to retain these events.

## Verification commands

```powershell
uv run pytest
cd frontend
npm run test
npm run build
```

## Pose-video labeling operations

Configure the video capability in `.env`:

```text
VIDEO_STORAGE_ROOT=data/video_labeling
POSE_MODEL_PATH=weights/pose.pt
VIDEO_WORKER_CONCURRENCY=1
```

Place yolo26m-pose-compatible COCO 17-keypoint weights at `weights/pose.pt`.
Missing weights do not prevent project administration, but the pose job fails
with the exact configured path and remains retryable.

Normal users should use the unified launcher:

```powershell
uv run python -m backend.scripts.start_app
```

For worker diagnostics or operator-controlled concurrency, the services can
still be run separately:

```powershell
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
uv run python -m backend.scripts.video_worker

# Diagnostics or an explicit local concurrency override:
uv run python -m backend.scripts.video_worker --once
uv run python -m backend.scripts.video_worker --concurrency 2
```

The local worker uses SQLite directly; Redis, Celery, and cloud queues are not
required. Pause, resume, cancel, retry, priority, progress, and error text
survive API restarts. On startup, orphaned `running` rows return to `queued`.
Multiple workers atomically claim distinct jobs.

Threshold/Model Process requests persist the requested final suggestion mode
and, for Model, pin the active compatible external model version. Only one
queued/running/paused pipeline is allowed per video. Suggestions remain separate
from manual segments.

Video deletion first stages only files prefixed by that managed video ID,
deletes the SQLite video row transactionally so dependent jobs and annotations
cascade, then finalizes the staged files. A database failure restores staged
files. Project-wide model packages, immutable export snapshots, unrelated
videos, and external source files are not removed.

Video storage is project scoped:

```text
data/video_labeling/<project_id>/
  raw/          immutable imported bytes
  canonical/    generated 24 FPS processing videos
  pose/         versioned compressed pose/tracking caches
  tracks/       optional track-derived filesystem caches
  features/     versioned compressed raw/transformed feature caches
  suggestions/  optional threshold suggestion artifacts
  model_predictions/ optional model prediction artifacts
  thumbnails/   cached video-card previews and fallbacks
  overlays/     optional rendered overlays
  models/       trusted-local inference artifacts
  exports/      atomically published export directories
```

Browser playback serves the owned raw import with suffix-appropriate media
type and byte-range support. Canonical OpenCV output is worker-only because
local builds may encode it as FMP4, which is not reliably browser-decodable.
Canonical frame synchronization remains timestamp based.

SQLite migrations run idempotently when `VideoRepository` opens the configured
database. Back up the database with SQLite's backup facility and retain the
project storage root together; either half alone is incomplete.

Video schema v2 adds `target_mode` and pinned `external_model_id` to persistent
jobs, normalizes legacy `model:<id>` stages to `model`, cancels duplicate active
legacy jobs deterministically, and creates partial unique indexes for one
active pipeline per video and one active model per project. The migration does
not rewrite raw videos, annotations, or large cache files.

Track edits invalidate only affected downstream artifacts; labels are never
silently deleted or moved into a review state. Editing an approved video clears
approval until it is validated again. Threshold profile edits invalidate
threshold caches only. External model versions and predictions remain separate.

Joblib/pickle artifacts can execute code and require explicit trusted-local
confirmation through the developer API. Model package paths, schema details,
thresholds, and classifier configuration are intentionally absent from the
annotator UI. Compatibility validation checks the exact class map, feature
schema/order, 60/12 window contract, 24 FPS, and adapter before Model processing
is enabled. ONNX uses `onnxruntime`; joblib packages are never silently trusted.

Export validation reports errors and unresolved/quality warnings. Generation
uses a staging directory and publishes by atomic rename only after annotation
JSONL, labelled keypoint NPZ, and the reproducibility manifest are complete.
Exports never create train/validation/test splits.
