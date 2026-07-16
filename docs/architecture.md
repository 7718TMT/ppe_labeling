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
one active model per project. Imports enqueue the workflow selected by the
annotator's Suggestions control.

API requests enqueue these stages and never run full-video inference or export
generation. Workers persist progress, errors, and control requests, publish
cache files atomically, and return orphaned `running` jobs to `queued` on worker
startup. Structured track/segment/window/history/model/export state is
transactional SQLite data; keypoint matrices, feature arrays, model artifacts,
and export files remain project-scoped filesystem artifacts.

### Event-driven workspace synchronization

The API server and `VideoWorker` are separate processes, so project workspace
updates cannot rely on in-memory pub/sub. `VideoRepository` writes compact,
project-scoped `video_workspace_events` outbox rows in the same SQLite
transactions as video, job, track, annotation, and export mutations.
`VideoWorkspaceSyncService` exposes a compact initial snapshot, cursor-based
delta reads, and a same-origin Server-Sent Events stream. The React workspace
opens one stream while visible; after a reconnect or hidden-tab restore it
replays only missed events, and it falls back to a snapshot when the bounded
outbox has expired the requested cursor. REST remains the mutation interface.

This replaces fixed-interval full `/videos`, `/jobs`, and `/exports` polling.
Small event payloads update cards and queue state directly; tracks and segments
remain lazy resources and are refreshed only for the active affected video.
See `docs/video-workspace-sync.md` for route and lifecycle details.

When a Threshold or Model stage completes for an initially unlabeled video, the
worker materializes generated source records as editable video segments. The
segments retain their suggestion ID and source for provenance; regeneration does
not replace existing annotations.

### Revision-aware annotation derivatives

Manual segment, worker, inclusion, and history edits advance the video's
annotation revision. Their backend mutation transaction also records a
dedicated annotation-derivative refresh request instead of the suggestion
pipeline. The request is coalesced per video in SQLite and may be deferred
until an active pipeline reaches a terminal state.
The `annotation_derivatives` worker stage rebuilds only the label-derived
windows and feature artifacts needed by export and later training; it never
executes Threshold or Model inference and never materializes new suggestion
segments. The Suggestions control is therefore the sole intentional trigger for
new generated labels.

Each derivative job records the revision it serves. If another edit arrives
while it is waiting or running, stale partial output is discarded and the
newest requested revision is queued, keeping exported derivatives consistent
with the saved annotation timeline without unnecessary repeated work.

Suggestion materialization follows the same durability rule. It writes the
complete generated segment set, its provenance/history, and a deferred
derivative intent atomically. The terminal Threshold or Model job promotes that
intent to `annotation_derivatives`; therefore a worker restart after labels are
committed cannot strand an export with stale window or feature artifacts.

Manual worker merge and split operations also stage a new immutable pose
artifact version. Their SQLite transaction switches `pose_cache_version` only
alongside the changed worker rows, annotation revision, derivative intent, and
outbox events. A pre-commit process crash therefore leaves the old artifact
pointer authoritative; a newly written but unreferenced pose artifact is safe
to clean up later.

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
