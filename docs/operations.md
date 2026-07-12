# Operations Guide

## Configuration and local execution

Copy `.env.example` to `.env` and run commands from the repository root. Paths
in `DATABASE_PATH` and task-profile settings are relative to that working
directory unless absolute paths are supplied.

```powershell
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
cd frontend
npm run dev
```

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
