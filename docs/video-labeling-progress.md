# Video Labeling Implementation Progress

Last updated: 2026-07-13

## Source-of-truth and baseline

- [x] Read `AGENTS.md`, `docs/final_video_labeling_specs.md`,
  `docs/ml_feature_list.md`, `docs/architecture.md`, and root `DESIGN.md`.
- [x] Confirmed the requested `docs/final-video-labeling-spec.md` and
  `docs/DESIGN.md` paths do not exist. The untracked 39-section
  `docs/final_video_labeling_specs.md` and root `DESIGN.md` are used without
  rewriting either source document.
- [x] Inspected the existing Controller-Service-Repository backend, filesystem
  image dataset repository, SQLite approval repository, task profiles, API
  schemas/controllers, React/Vite routes, workspace hooks, panels, canvas,
  filmstrip, tests, Tailwind tokens, and operational documentation.
- [x] Confirmed the only pre-existing working-tree files are the two untracked
  source-of-truth documents. They will not be overwritten.
- [x] Backend baseline: `59 passed` with one Starlette/httpx deprecation warning.
- [x] Backend compile baseline: passed with the project Python 3.12 interpreter.
- [x] Frontend baseline: `11 passed`; production build passed.
- [x] No lint script is configured. Vite reports existing deprecated plugin
  options and the existing bundle-size warning.
- [x] The shell default Python 3.14 does not have pytest; project checks use
  `.venv/Scripts/python.exe` (Python 3.12.13).
- [x] `weights/pose.pt` is absent. Real pose jobs will report an actionable
  missing-weight failure; synthetic fixtures and all non-pose workflows remain
  usable.

## Existing UI/design audit

- Application shell: 48px top toolbar, collapsible fixed side panels, fluid
  central stage, bottom filmstrip, task breadcrumbs, save/action status.
- Tokens: charcoal/teal tonal surfaces, 4px spacing baseline, Inter interface
  typography, JetBrains Mono metadata, ghost outlines, small radii, and solid
  teal active/focus states.
- Interaction patterns: icon tooltips, segmented controls, compact technical
  controls, explicit empty/loading/error states, autosave status, confirmation
  before destructive/bulk actions, keyboard-first editing, responsive sidebar
  collapse.
- Video-specific justified differences: a media player replaces the image
  canvas; the filmstrip becomes a multi-layer temporal timeline; the right
  properties panel becomes track/segment/suggestion/feature inspection; a
  virtualized browser and persistent queue are added to the left side.

## Execution checklist

- [x] SQLite migrations and structured video metadata.
- [x] Versioned filesystem storage, import, probing, canonical mapping.
- [x] Persistent jobs, lifecycle controls, worker, and restart recovery.
- [x] Pose cache, tracking cache, track correction, and selective invalidation.
- [x] Manual segments, validation, optimistic concurrency, history, undo/redo,
  approval, and recovery state.
- [x] Groups A-E raw features, transforms, quality/provenance (tests pending).
- [x] Threshold profiles/suggestions and auditable review actions.
- [x] Trusted-local model package validation/inference and separated provenance.
- [x] Deterministic windows, QC review, atomic exports, and manifest.
- [x] React/Vite browser, queue, workspace, timeline, inspectors, profile/model/
  export views, shortcuts, and API integration.
- [x] Full regression, documentation, and acceptance audit.
- [ ] Automated visual screenshot verification (the in-app browser exposed no
  browser instance in this session; manual steps are listed below).

## Implementation decisions

- SQLite remains the source for structured workflow metadata. Raw/canonical
  videos and large pose/feature/export arrays use project-scoped versioned files.
- Canonical annotations use inclusive integer frame boundaries, matching the
  specification examples and window `[start, end]` notation.
- Editing an approved video immediately invalidates approval and records the
  change in annotation history.
- Controllers remain thin; workflow/invalidation lives in video services and
  persistence remains in repositories. The existing image annotation service is
  unchanged.

## Final verification

- Backend: `94 passed`; Python compile passed.
- Frontend: `51 passed`; TypeScript/Vite production build passed.
- Real YOLO pose smoke: official yolo26m-pose weights were retrieved to
  `weights/pose.pt`; CPU inference found one person with `[1, 17, 2]`
  keypoints on an existing PPE image.
- Existing image annotation tests remain in the full backend/frontend suites.
- No training, split management, evaluation, or mock production API was added.
- Human classes are constrained in project config, schemas, SQLite checks,
  services, TypeScript unions, controls, windows, suggestions, and exports.
- The requested source files remain unmodified and untracked.

## Acceptance criteria audit

All 22 criteria in section 39 are implemented and covered by automated tests,
code-level checks, or the real pose smoke. Persistent jobs and versioned pose
caches make videos independent/resumable; annotations become available at
tracking readiness; all three track correction categories are exposed; Groups
A-E, normalized scores, thresholds, external adapters, review provenance,
60/12 windows, QC exclusion, atomic exports, restart recovery, and selective
invalidation are present.

Automated visual comparison could not be completed because the in-app browser
was unavailable. Manually verify at desktop and narrow widths:

1. Start the unified launcher, open `/`, and confirm the PPE, Sign, and Pose
   module cards share the existing shell.
2. Open Pose, create a project, import a small video, and use the split Process
   button; the worker is already managed by the launcher.
3. Confirm left/right panels collapse below 900/1200px, the player remains the
   fluid stage, and the timeline scrolls at zoom above 1x.
4. Confirm human segments are solid, Threshold suggestions translucent/solid
   outline, and AI suggestions dashed; switch `Off | Threshold | AI`.
5. Check focus states, empty/loading/failure/conflict/low-quality messages,
   queue progress and controls, model mismatch tooltip, and export validation.

## Playback and end-user UX corrective pass (2026-07-13)

### Inspection and baseline

- [x] Re-read `AGENTS.md`, the complete 39-section final specification,
  `docs/ml_feature_list.md`, `docs/architecture.md`, and root `DESIGN.md`.
- [x] Preserved the existing dirty worktree containing the pose-video feature;
  no unrelated user changes were reverted.
- [x] Baseline backend: `78 passed`; compile passed.
- [x] Baseline frontend: `15 passed`; production build passed.
- [x] No lint script is configured. Existing warnings remain the Starlette/httpx
  deprecation, Vite plugin deprecations, and the main bundle size warning.
- [x] The in-app browser exposed no browser instance, so interactive visual
  reproduction is unavailable. Code, real cache metadata, media decoding, and
  automated lifecycle tests are used; manual visual verification remains due.

### Confirmed causes and decisions

- [x] Both stored raw videos decode through their actual final frame and use
  H.264. Their canonical caches also contain every frame and complete pose data,
  but are encoded as FMP4 by OpenCV. The media endpoint incorrectly preferred
  this less browser-compatible worker cache over the browser-compatible raw
  import. The raw owned copy is now the playback source; canonical media remains
  worker-only and frame synchronization continues through canonical timestamps.
- [x] The React player reused one media element across video identity changes
  without an explicit unload/load cycle. Frame callbacks and async overlay/data
  responses also lacked video-generation guards, allowing stale state after
  A-to-B-to-A navigation. The media lifecycle and all active-video response
  commits are now identity guarded.
- [x] End-user presentation maps detailed internal status to only Unprocessed,
  Processing, Ready, or Failed; annotation status is separately Unlabeled, In
  progress, or Completed. Worker stage names remain internal.
- [x] Threshold/model numeric and package configuration remains available only
  through backend developer contracts. Annotators see only Threshold or Model.

### Corrective implementation checklist

- [x] Continuous playback and A-to-B-to-A media reload lifecycle.
- [x] Missing-pose playback independence and frame/overlay synchronization.
- [x] Plain video statuses and progress-stage labels without Canonicalize.
- [x] Cached thumbnails, bordered compact video cards, and safe video deletion.
- [x] Split Process control with remembered Threshold/Model mode.
- [x] Unified PPE, Sign, and Pose homepage within the existing React shell.
- [x] Three right-panel tabs: Annotate, Suggestions, and Details.
- [x] Searchable, dismissible Pose Help guide.
- [x] One-command API, worker, and frontend launcher.
- [x] Persistent mode-aware processing queue and final regression pass.
- [x] User guide, architecture, operations, README, and progress refresh.
- [ ] Manual visual verification (automated in-app browser unavailable).

### Final corrective-pass verification

- [x] SQLite schema v2 migrates legacy model job stages, persists Threshold or
  Model intent, pins the compatible model ID, and enforces one active pipeline
  per video and one active model per project.
- [x] Fresh imports remain Unprocessed until the annotator selects Process.
  Same-mode duplicate requests reuse the job; a conflicting active mode returns
  `409`; worker successors are committed atomically.
- [x] Raw owned media is served with byte-range support. The React player
  explicitly unloads/reloads sources, handles actual media end independently of
  pose length, fits the video and SVG in the same viewport, retains overlays in
  fullscreen, and reports unsupported/damaged media without hiding annotation
  data.
- [x] Overlay ranges are fetched in bounded chunks and cached per video instead
  of issuing and discarding one request per playback frame.
- [x] Existing-segment edits autosave with optimistic revisions and truthful
  Unsaved/Saving/Saved feedback. Workspace recovery writes are serialized so a
  late video-A request cannot overwrite newer video-B state.
- [x] Optional feature/window/model-availability failures no longer block
  manual annotations. Worker completion refreshes derived data without
  resetting local segment boundary drafts.
- [x] Backend `uv run pytest -q`: `94 passed`; compileall passed.
- [x] Frontend `npm run test -- --reporter=dot`: `14` files and `51` tests
  passed; `npm run build` passed.
- [x] `git diff --check` and route/contract inspection completed.
- [x] No training, dataset splitting, evaluation, or mock production API was
  introduced; human classes remain exactly others, running, and falling.

### Corrective-pass visual and operational limitations

- Automated browser screenshots could not be produced because the in-app
  browser exposed no browser instance. The desktop/narrow-layout and repeated
  real playback checks below remain manual verification, not an automated pass.
- Playback uses the untouched owned import to avoid unreliable OpenCV FMP4
  output. A codec unsupported by the local browser still cannot decode, but the
  UI now shows a concise media error while preserving overlays and annotations.
- Motion details intentionally remain a read-only compact score/heatmap view
  under Details; numeric threshold and model configuration stays out of the
  annotator interface as required by this UX pass.
