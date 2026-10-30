# Application architecture

A local application for PPE/Sign image annotation and Behavior video labeling
and inference. One React frontend connects to FastAPI; a separate worker handles
durable Behavior video jobs. Model training is outside this application.

## Runtime components

```text
Browser (React)
  | REST commands, media requests, workspace SSE
  v
FastAPI --------------------> Local filesystem
  |                           images, labels, videos, models, caches, exports
  v                                    ^
SQLite <------------------ VideoWorker-+
metadata, jobs, events      claims jobs and publishes video artifacts
```

The [launcher](../README.md#run-the-app) starts Vite, FastAPI and VideoWorker.
The API and worker share SQLite and configured storage roots. SQLite is also
the job queue and event outbox; no external broker is required. PPE/Sign
inference runs synchronously in API requests, including its video uploads.
The API currently has no authentication; see [limitations](KNOWN_LIMITATIONS.md).

## Technology stack

| Area | Technology | Role |
|---|---|---|
| Frontend | React, TypeScript, Vite, React Router | Workspaces and navigation |
| UI and drawing | Tailwind CSS, Lucide, Konva/react-konva, SVG | Styling, image boxes and video overlays |
| Backend | Python 3.12, FastAPI, Uvicorn, Pydantic | HTTP API and validation |
| Database | SQLite via Python `sqlite3`, WAL mode | Metadata, jobs and workspace events |
| File storage | Local filesystem | Media, labels, weights, caches and exports |
| Detection/tracking | Ultralytics YOLO/YOLO-Pose, BoT-SORT with ReID | Detections, keypoints and worker identities |
| Model runtime | PyTorch/torchvision, CPU or NVIDIA CUDA | Detector and pose inference |
| Behavior inference | Joblib, XGBoost/scikit-learn; ONNX Runtime for external ONNX packages | Compatible pretrained classifiers |
| Video/features | OpenCV, FFmpeg via imageio-ffmpeg, NumPy | Media processing and motion features |
| Background processing | Python VideoWorker, SQLite jobs, SSE | Durable jobs and workspace updates |
| Tests/tooling | pytest, HTTPX, Vitest, Testing Library; uv, npm | Checks and dependencies |

Exact versions: [pyproject.toml](../pyproject.toml), [uv.lock](../uv.lock),
[package.json](../frontend/package.json), [package-lock.json](../frontend/package-lock.json).

## Application boundaries

Dependencies flow `controllers -> services -> repositories -> SQLite/files`.

| Layer / location under `backend/app/` | Responsibility |
|---|---|
| `api/controllers/`, `api/schemas/`, `api/dependencies/` | Validate HTTP input, resolve dependencies, call services and serialize results; grouped by image/video capability |
| `services/` | Coordinate annotation, inference, features, exports and reconciliation |
| `repositories/` | Own SQL transactions, migrations and filesystem access |
| `domain/` | Framework-independent values, geometry and expected errors |
| `inference/`, `core/` | Detector adapters, task profiles, settings and device resolution |

Controllers do not write SQL/files directly. Repositories do not depend on
FastAPI. Domain errors map to HTTP responses at the API boundary. PPE and Sign
share the image workflow through task profiles; video tracks, timelines and
jobs stay in dedicated video services.

## Processing flows

| Capability | API boundary | Flow |
|---|---|---|
| PPE/Sign labeling | `/api/v1/tasks/{task}` | Upload/list images -> edit or auto-label -> save YOLO labels -> approve/export |
| PPE/Sign inference | `/api/v1/tasks/{task}/inference` | Upload image/video -> synchronous detector/rendering -> separate stored results |
| Behavior labeling | `/api/v1/video-projects` | Create project/import -> enqueue processing -> review/edit tracks and segments -> approve -> enqueue export |
| Behavior inference | `/api/v1/behavior-inference` | Import into an internal project -> worker pipeline -> raw probabilities and smoothed read-only events |

### Image workflow

- `AnnotationService` coordinates labels and approval. `DatasetRepository`
  owns images/YOLO files; `ApprovalRepository` owns approval state.
- Detector selection comes from the task profile through `detect(image_path)`.
  Models load lazily for AI actions. Ordinary labeling/media/export paths do
  not construct a detector.
- `MediaService` and `DatasetExportService` use the filesystem repository
  directly; media and ZIP reads do not initialize approval storage.
- Labels use the image stem as key. Uploads ensure unique stems across
  extensions; manually introduced collisions block affected operations.

### Behavior worker pipeline

```text
canonicalize -> pose_track -> features/windows -> threshold OR model
annotation edit -> annotation_derivatives (windows/features only)
approved project selection -> export:<id>
```

- Canonical processing uses **24 FPS** with timestamp-based
  `canonical_frame_mapping`; it is not a duration-only conversion. Windows use
  60 frames with stride 12.
- Jobs persist their target mode and selected external model. SQLite enforces
  one active pipeline per video and one active external model per project.
  Workers atomically claim jobs; progress, errors and control requests survive
  process restarts. Startup requeues orphaned running jobs.
- Initial Threshold/Model outputs become editable segments with provenance.
  Automatic materialization preserves existing annotations; an explicit
  Suggestions action can replace them after confirmation.
- Read-only inference reuses the pipeline in an internal project hidden from
  labeling projects. It skips annotation materialization, stores raw window
  probabilities, then forms events with centered three-window smoothing and
  same-class temporal merging.
- Classifier manifests define feature order, preprocessing and class/window
  compatibility. The fixed classifier defaults to the legacy XGBoost contract
  when no manifest is supplied. See [model configuration](OPERATIONS.md#class-maps-and-behavior-model-contract).

## Data ownership and persistence

| Data | Authoritative storage |
|---|---|
| Image inventory, YOLO labels, visualizations | Task-specific filesystem directories; no image catalog in SQLite |
| Image approvals | SQLite `approval_status`, keyed by task/filename; current state only, no approval audit history |
| Video projects, jobs, tracks, segments, history, windows, model/export metadata | SQLite via `VideoRepository` |
| Video media, versioned pose/features, model packages and export payloads | Project directories via `VideoStorageRepository` |
| PPE/Sign inference source, rendered results and item metadata | Separate filesystem root, isolated from labeling datasets |

SQLite migrations run when the video repository opens. Structured state and
large files are deliberately separate: a restorable workspace needs both the
database and its storage trees. A training export is not a full backup.
See [database schema](DATABASE.md), [export contract](DATA_EXPORT.md) and
[backup/restore](OPERATIONS.md#handover-backup-and-restore).

## Consistency and recovery

- **Video artifacts:** write temporary/staged output and publish completed
  artifacts atomically. Export directories appear only after all payloads are
  complete. Publication and DB pointers remain separate coordination steps.
- **Annotation derivatives:** edits advance a revision and record refresh
  intent in the same transaction. Requests coalesce per video and can wait for
  an active pipeline. Jobs discard stale output and schedule the latest
  revision; they never run suggestion inference. Suggestion materialization
  also commits derivative intent, preventing stale exports after a restart.
- **Worker merge/split:** stage a new immutable pose version, then commit its
  pointer with worker rows, revision, derivative intent and events. Before
  commit, the old pose version remains authoritative.
- **Workspace sync:** mutations write SQLite outbox events transactionally.
  The browser starts with a snapshot, consumes SSE while visible, and replays
  cursor-based deltas after reconnect/visibility restore. Expired cursors
  trigger a fresh snapshot. REST remains the mutation interface; large
  track/segment resources load lazily rather than through full-list polling.
- **Image rename/delete:** filesystem and approval changes are not one
  transaction. Partial failures return `reconciliation_required: true` with
  operation details; operators inspect files and reconcile stale approvals.
  See [recovery procedures](OPERATIONS.md#destructive-workflow-behavior).

## Frontend and media boundary

One React router serves all modules. Feature hooks compose API calls, editing
and workspace state; backend package layout is not part of the UI contract.

The browser plays the project-owned raw video through range-enabled media
responses. Canonical video is a worker cache, since its encoding may not be
browser-compatible. Playback timestamps map to canonical indices for overlays.
Video/SVG overlays share a fitted viewport; bounded per-video chunk caches
avoid a pose request per frame. Video-switch guards prevent stale responses
from updating another video's workspace.

The UI keeps processing status separate from annotation progress. Detailed
model settings remain backend contracts. For controls and shortcuts use
[USER_GUIDE](USER_GUIDE.md); for endpoints/settings use [API](API.md) and
[CONFIGURATION](CONFIGURATION.md). Detailed formulas are in
[Behavior features](FEATURES_FOR_BEHAVIOR_DETECTION.md).
