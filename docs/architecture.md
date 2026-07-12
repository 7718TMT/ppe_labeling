# Application Architecture

This application uses a layered Controller-Service-Repository design around a
shared image annotation workflow. It intentionally does not create a separate
full stack for PPE and safety-sign profiles: profiles supply configuration and
model adapters, while the workflow remains shared.

## Dependency direction

```text
FastAPI controllers
        -> application services
        -> repositories
        -> filesystem or SQLite

Application services -> domain models, inference adapters, visualization services, core utilities
```

Dependencies flow downward. Repositories do not import FastAPI, controllers do
not write files or SQLite rows directly, and inference modules do not depend on
API schemas or storage implementations.

## Backend packages

```text
backend/app/
  api/
    controllers/       HTTP route definitions and response mapping
    dependencies.py    FastAPI dependency wiring
    errors.py          application-error to HTTP-response mapping
    schemas.py         Pydantic request and response contracts
    router.py          router registration
  core/                configuration and device resolution
  domain/              framework-independent models, errors, and geometry
  inference/           detector protocol and detector implementations
  repositories/        filesystem dataset persistence and SQLite approvals
  services/            annotation workflows, labels, visualizations, reconciliation
```

### Controllers

Controllers in `backend/app/api/controllers/` only validate HTTP input, resolve
dependencies, call an application service, and serialize the response. The
controllers are grouped by cohesive delivery concern: tasks, annotation,
exports, and media.

### Services

`AnnotationService` owns image-workflow sequencing: list/upload, labels,
approval state, delete, sequential rename, export, auto-label, and
visualization. `ApprovalReconciliationService` is the maintenance workflow that
compares filesystem image names with SQLite approval rows.

`LabelingService` and `VisualizationService` are focused collaborators. They
are not HTTP-aware. Auto-label endpoints use an inference-enabled
`AnnotationService`; normal list, media, export, and persistence requests do
not construct a detector.

### Repositories and data ownership

`DatasetRepository` owns low-level filesystem operations for the task's images,
YOLO label files, visualizations, uploads, rename mechanics, and ZIP contents.
`ApprovalRepository` owns only current approval state in SQLite. There is no
database-backed image catalog: image inventory is derived from filesystem files.

`MediaService` and `DatasetExportService` use `DatasetRepository` directly, so
media serving and ZIP generation do not initialize SQLite. Approval-aware image
listing and approval-mutating workflows continue to use `AnnotationService`.

YOLO labels and generated visualizations are keyed by image stem. The repository
therefore keeps uploaded image stems unique across extensions and rejects manual
same-stem collisions before an edit, export, auto-label, visualization, delete,
or sequential-rename workflow could apply one artifact to two images.

The SQLite table is:

```text
approval_status(task_id, filename, is_approved, updated_at)
primary key: (task_id, filename)
```

Unapproving deletes the approval row, so SQLite represents current approval
state rather than an approval audit history.

### Domain models and API schemas

`backend/app/domain/models.py` contains internal values such as `BoundingBox`,
`ImageRecord`, `DeleteImageResult`, and `RenameDatasetResult`. Pydantic models
in `backend/app/api/schemas.py` describe only external JSON contracts and map at
the controller boundary.

Expected application errors live in `domain/errors.py`; `api/errors.py` maps
them to the established HTTP status codes. A partially completed destructive
operation returns a 500 response with `reconciliation_required: true` and an
`operation` object describing the completed state and warnings.

## Task profiles and inference

`core/config.py` builds the configured PPE and safety-sign profiles from `.env`.
Both profiles share the annotation service but select a detector through the
`inference.Detector` protocol:

```text
detect(image_path) -> list[BoundingBox]
```

Detector implementations are synchronous because the application is currently
single-user and inference is CPU/GPU-bound. They load models lazily on the first
auto-label request. Device selection remains in `core/device.py`.

## Frontend boundary

The React/Vite frontend is deliberately organized around the annotation user
experience rather than mirroring backend folders. Its task-scoped API client is
in `frontend/src/api/client.ts`; feature hooks compose workspace data, annotation
editing, and actions. It consumes task-scoped JSON and media URLs only, so
backend folder movement is not part of its contract.

## Future capability guidance

Video annotation must be introduced as a separate capability when it is needed.
It may reuse neutral configuration, geometry, detector, logging, and safe-path
utilities, but must not add clip, frame, temporal, track, or playback state to
the established image annotation workflow.
