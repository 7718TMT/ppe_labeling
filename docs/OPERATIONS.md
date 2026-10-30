# Operations Guide

## Configuration and local execution

Follow [README](../README.md#install) for installation and
[startup/shutdown](../README.md#run-the-app). Run commands from the repository root. Paths
in `DATABASE_PATH` and task-profile settings are relative to that working
directory unless absolute paths are supplied.

Unless labeled otherwise, shell blocks below contain commands valid in Windows
PowerShell, Linux Bash and macOS Zsh/Bash. `text`, `json` and `sql` blocks are
file contents or reference examples, not shell commands.

### Platform notes

| Platform | Current dependency/device configuration |
|---|---|
| Windows/Linux | `uv sync` selects the CUDA 13.2 PyTorch index. Inference uses CUDA when available, otherwise CPU. Compatible wheels and OS/driver libraries are still required. |
| macOS Apple Silicon, 14+ | The lockfile includes ARM64 macOS PyTorch wheels. `INFERENCE_DEVICE=auto` resolves to CPU; MPS is not implemented in the device selector. |
| macOS Intel | The locked PyTorch/torchvision versions have no Intel macOS wheels. The current install instructions do not support this target; dependency changes need separate validation. |

These notes describe configuration and wheel availability, not completed Linux
or macOS end-to-end validation. Verify on the receiving machine with the
[handover checklist](handover/CHECKLIST.md). The platform index selection follows
[uv's PyTorch integration](https://docs.astral.sh/uv/guides/integration/pytorch/).

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

```sh
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

```sh
uv run python -m backend.scripts.reconcile_approvals --task ppe
```

Remove only the rows reported as stale:

```sh
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

### Class maps and Behavior model contract

Class maps use `ID=Name` entries separated by `|`. To add an image class, update
the task map and provide a detector trained with matching IDs. The backend filters
AI detections and rejects manual classes outside that map; the UI uses the map.
Defaults and paths are listed in [CONFIGURATION](CONFIGURATION.md).

`BEHAVIOR_MODEL_PATH` selects a trusted joblib classifier exposing `predict_proba`
(for example XGBoost or Extra Trees). For a non-legacy artifact, set
`BEHAVIOR_MODEL_MANIFEST_PATH` to its exact training contract:

```json
{
  "name": "Behavior Extra Trees",
  "version": "your-model-version",
  "class_map": {"others": 0, "running": 1, "falling": 2},
  "feature_schema_version": "v1",
  "feature_columns": ["...replace with the exact ordered feature names..."],
  "window_length": 60,
  "stride": 12,
  "canonical_fps": 24,
  "preprocessing": "raw",
  "inference": {"minimum_probability": 0.5, "maximum_merge_gap": 12}
}
```

Generate the ordered names with `video_features.feature_columns()` from
`backend.app.services`. Use `raw` for all 143 unchanged features;
`behavior_preprocess_v1` requires its 141-column order and legacy transforms.
See [Behavior features](FEATURES_FOR_BEHAVIOR_DETECTION.md#raw-features-threshold-scores-and-model-preprocessing).
The placeholder list above must be replaced before use. Leave the manifest
setting unset only when the artifact matches the legacy contract.

## Troubleshooting

### Port checks

Find listeners on ports 8000/5173 using the appropriate shell:

| OS / shell | Read-only command |
|---|---|
| Windows PowerShell | `Get-NetTCPConnection -State Listen -LocalPort 8000,5173 -ErrorAction SilentlyContinue` |
| Linux Bash | `ss -ltnp` (inspect the local port column for 8000/5173; requires `ss` from iproute2) |
| macOS Zsh/Bash | `lsof -nP -iTCP:8000 -iTCP:5173 -sTCP:LISTEN` |

Ask the listener's owner to stop it cleanly before launching the app.

### Runtime and dependencies

| Problem | Check / action |
|---|---|
| Missing model or class mismatch | Check the configured path and class/feature contract. The active video tracker also needs `weights/reid.pt`. |
| Missing or wrong image inventory | Check the selected task and configured image/label paths. |
| Partial rename/delete | Inspect affected files first; use the [reconciliation procedure](#approval-reconciliation) for stale approval rows. |
| Frontend cannot reach backend | Check the launcher, ports, `CORS_ORIGINS` and Vite/reverse-proxy routing. |
| Python/dependency error | Confirm Python 3.12 and run `uv sync` with the checked-in lockfile. |
| Interrupted video job | Arrange a clean restart with the operator; worker startup requeues orphaned running jobs. Check the queue and retry failed jobs. |
| macOS XGBoost reports missing `libomp.dylib` | Install the OpenMP runtime; with Homebrew, run `brew install libomp` in Zsh/Bash, then retry. |

For CUDA issues, inspect the installed build and availability:

```sh
uv run python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
```

The locked Windows/Linux build should report CUDA 13.2 (`+cu132`). If CUDA is
absent from the build, check `uv sync` and the lockfile. If availability is False,
check the NVIDIA driver and GPU visibility. `INFERENCE_DEVICE=cpu` intentionally
uses CPU. On macOS, CUDA version `None` and CUDA availability `False` are expected;
do not apply the Windows/Linux CUDA build check there. XGBoost's platform
capabilities are described in its [installation guide](https://xgboost.readthedocs.io/en/stable/install.html).
Retain the task/project, filename, action and error log when escalating.

## Verification commands

```sh
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

Use the [unified launcher](../README.md#run-the-app) for normal operation.

For worker diagnostics or operator-controlled concurrency, the services can
still be run separately. Run the API and worker in different terminals;
the diagnostic commands are alternative worker invocations, not extra workers:

```sh
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

## Handover backup and restore

A training export is a sample delivery, not a workspace backup. Preserve all
configured storage locations, including paths outside the repository if used.

### Create a consistent backup

1. Record the tested source commit, dependency lockfiles, configuration paths,
   model versions and selected artifact hashes. Keep real configuration/secrets
   in a separate protected channel, not in Git.
2. Arrange a maintenance window with the operator. Wait for active work to
   finish and ask the owner to stop the launcher cleanly with Ctrl+C. Ensure
   other API/worker instances using this dataset are also stopped by their owners.
   Do not kill processes or copy a changing workspace for a handover snapshot.
3. Copy the configured `DATABASE_PATH`, PPE and Sign image/label/visualization
   directories, `VIDEO_STORAGE_ROOT`, and `IMAGE_INFERENCE_STORAGE_ROOT` if
   inference history is being retained. Retain the complete video project roots,
   including raw media, models, pose/features and export artifacts, so persisted
   artifact references remain valid. Include the original configuration-path map.
4. Prefer SQLite's backup API to create the database snapshot, including after a
   clean stop. For an offline file copy, retain any remaining `-wal` and `-shm`
   companions with the main file; never copy only a live main database file.
   A database-only online backup does not synchronize filesystem artifacts.
5. Archive the snapshot, calculate its SHA-256 and record it in the private
   delivery message. Keep the source workspace intact until restore succeeds.

### Restore and verify

1. Use a separate disposable directory. Install the recorded source commit and
   dependencies. Do not overwrite the operator's active dataset or database.
2. Restore the database and complete corresponding storage trees. Set `.env`
   paths to the restored copy, preserving internal project-relative structure;
   restore external model paths or deliberately update them for the test copy.
3. Verify required models and class/feature contracts before opening the app.
   Starting the video repository applies migrations; keep the original snapshot
   unchanged in case rollback to the recorded source version is needed.
4. Use separate ports or arrange a clean stop of the test instance before
   starting the restored copy. Check images, labels, approvals, video playback,
   worker timelines and completed exports. Only then test a new job on a sample.
   The worker can reclaim stale running jobs on startup; confirm the snapshot
   has no unexpected work before launching it.
5. Report restore results and outstanding issues to the recipient.
   If restore fails, preserve logs and investigate the test copy. Rollback means
   returning to the preserved snapshot with its matching source/configuration,
   not deleting or modifying the live workspace.

## Maintaining generated references

Run from the repository root:

```sh
uv run python -m backend.scripts.generate_docs
uv run python -m backend.scripts.generate_docs --check
```

The command generates CONFIGURATION, API and DATABASE Markdown references.
OpenAPI is used in memory to build API.md; no OpenAPI JSON file is published.
Historical design notes live under `docs/archive/` and are not generated or
updated by this command.
Configuration comes from code defaults and `.env.example`, never `.env` or
environment overrides. OpenAPI is built without requests or server startup.
Database introspection applies the real migrations to a temporary SQLite file.
No models are loaded and no live database or worker is opened. Generated files
carry a do-not-edit notice, source references, generation date (Asia/Saigon) and
checkout commit. Edit the generator scripts for document wording changes. The
date is retained when content and commit are unchanged, so the calendar alone
does not create drift. In source copies without Git metadata the commit is
recorded as `unavailable`; no commit is invented. Markdown prose outside the
generated markers is preserved for compatibility, but edits belong in the
generator scripts. `--check` exits 1 for missing/stale
output and writes no documentation; generation errors also fail the command.

Each generator can be invoked independently as
`backend.scripts.generate_configuration_docs`, `backend.scripts.generate_api_docs`
or `backend.scripts.generate_database_docs`, with the same `--check` option.
Each changed output is replaced atomically after rendering; the set of files is
not a multi-file transaction. Rerun after a publication error to finish the set.

Handwritten guides, limitations and ownership require human review; they are
not inferred by the generator.
