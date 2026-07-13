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

## Capability boundary guidance

Video annotation remains a separate capability from image annotation. It may
reuse neutral configuration, geometry, detector, logging, and safe-path
utilities, but must not add clip, frame, temporal, track, or playback state to
the established image annotation workflow.

## Pose-video labeling capability

Pose-video labeling is implemented beside, not inside, the image workflow. Its
controllers call dedicated project, annotation, feature, model, and export
services. Those services coordinate `VideoRepository` (versioned SQLite
metadata) and `VideoStorageRepository` (raw/canonical video plus versioned large
artifacts). The existing `AnnotationService`, image controllers, task profiles,
and image filesystem contract are unchanged.

Heavy stages are SQLite jobs claimed by dedicated `VideoWorker` processes:

```text
canonicalize -> pose_track -> features -> threshold
                              -> model (on request)
project      -> export:<id>   (on request)
```

Each video pipeline persists its requested `target_mode`; Model pipelines also
pin `external_model_id` independently of the stage name. SQLite schema v2 adds
those fields and partial unique indexes for one active pipeline per video and
one active model per project. A fresh import remains unprocessed until the
annotator uses the Process control.

API requests enqueue these stages and never run full-video inference or export
generation. Workers persist progress, errors, and control requests, publish
cache files atomically, and return orphaned `running` jobs to `queued` on worker
startup. Structured track/segment/window/history/model/export state is
transactional SQLite data; keypoint matrices, feature arrays, model artifacts,
and export files remain project-scoped filesystem artifacts.

The React/Vite video routes reuse the image application's toolbar, tonal panel,
typography, spacing, focus, feedback, and responsive-collapse conventions. The
video player, pose overlay, virtualized browser, queue, multilayer timeline,
feature details, window review, and export validation are intentionally
video-specific components.

The root React router is the single product shell for PPE, Sign, and Pose. The
homepage links to the two task-scoped image workspaces and the project-scoped
Pose workspace; no second frontend or standalone Pose shell is created. The
local launcher starts Vite, FastAPI, and the persistent worker as one managed
runtime command.

Browser media is the immutable project-owned raw import, served with range
support and its suffix-specific content type. Canonical video remains a worker
cache because OpenCV may produce FMP4 output that is suitable for pose inference
but not reliable in HTML video decoders. Canonical frame indices are still
derived from media timestamps. The React player explicitly unloads and reloads
when video identity changes, and generation guards prevent stale media-frame,
overlay, track, segment, feature, or suggestion responses from crossing video
boundaries.
The fitted video and SVG share one `object-contain` viewport. Overlay frames are
loaded in bounded chunks and cached per video, so normal 24 FPS playback does
not issue or discard one HTTP request per frame. Fullscreen targets this shared
viewport and therefore retains skeletons, boxes, and track IDs.

Detailed pipeline stages remain backend state. The annotator UI maps videos to
Unprocessed, Processing, Ready, or Failed and keeps annotation progress
separate. Developer model packages and threshold configuration remain backend
contracts; the end-user processing surface exposes only Threshold or Model.
