# Video workspace synchronization

The Pose workspace uses an event-driven synchronization path for project-level
state. It replaces repeated full reads of videos and processing jobs while
preserving the existing REST commands for imports, edits, processing, exports,
and deletion.

## Why this exists

The API server and the persistent video worker are separate local processes.
An in-memory event bus would lose updates on a restart and would not cross that
process boundary. `video_workspace_events` is therefore a durable SQLite
outbox. Every relevant repository mutation writes its state and its event in
the same transaction.

The browser can reconnect with its last event ID. If that ID is no longer
within the retained outbox history, the server explicitly requests a fresh
snapshot instead of applying an unsafe partial update.

## API contract

| Route | Purpose |
| --- | --- |
| `GET /api/v1/video-projects/{project_id}/workspace-snapshot` | One compact initial/recovery read: project, video cards, jobs, processing options, exports, and `last_event_id`. |
| `GET /api/v1/video-projects/{project_id}/workspace-changes?after={event_id}` | Cursor-based REST fallback used after reconnecting or restoring a hidden tab. |
| `GET /api/v1/video-projects/{project_id}/events?after={event_id}` | Long-lived Server-Sent Events stream. The `Last-Event-ID` header is honored on browser reconnect. |
| `POST /api/v1/video-projects/{project_id}/videos/{video_id}/annotation-derivatives/refresh` | Explicit recovery/API request for a coalesced refresh of label-derived windows and features. Normal manual edits already create this intent server-side. It never creates suggestions. |

Event envelopes contain `event_id`, `project_id`, optional `video_id`,
`event_type`, compact `payload`, and `created_at`. Current event types are:

- `video.changed` — one card changed or was deleted.
- `job.changed` — one queued/running/completed/failed job changed. Progress
  events are coalesced to meaningful increments.
- `tracks.changed` — processing replaced the active video's worker tracks.
- `annotation.changed` — segment, history, inclusion, approval, or suggestion
  materialization changed the annotation revision.
- `export.changed` — one background export changed state.
- `resync.required` — the requested event cursor has expired; replace local
  shell state with a new snapshot.

Track and segment rows remain lazy resources. When an event affects the open
video, the browser coalesces the short burst into one tracks-and-segments
refresh rather than streaming large annotation payloads or reloading every
video card.

## Browser lifecycle

`useVideoWorkspaceSync` owns only transport concerns. `VideoWorkspace` owns
its normalized UI state and applies snapshots/events. The hook:

1. Fetches one snapshot on entry.
2. Opens one same-origin SSE stream after the returned cursor.
3. Closes that stream while the tab is hidden.
4. On visibility restore or stream failure, fetches only the missing event
   delta before reopening the stream.
5. Uses bounded jittered backoff for unavailable connections and falls back to
   a full snapshot only when the server asks for it.

The stream is read-only. Commands remain normal REST requests, so mutation
validation, revision conflicts, and controller-service-repository boundaries
are unchanged.

## Request and cache behavior

- The workspace no longer polls `/videos`, `/jobs`, or `/exports` on fixed
  intervals.
- The export dialog receives `export.changed` through the same stream. A
  completed export retains an explicit **Download ZIP** fallback.
- Pose overlays are fetched only when the overlay is visible, in 120-frame
  batches (five seconds at the canonical 24 FPS), and cached per video.
- The unused feature-window request was removed from the playback workspace.
- Workspace recovery writes are serialized, de-duplicated, and checkpointed at
  most once per five seconds during playback; pausing or changing the selected
  worker/source records the exact current frame.

Normal browser video range requests are intentionally unchanged: they are how
the media element streams the project-owned source file and are not workspace
polling.

## Annotation edits and derived data

Saving, deleting, merging, resizing, undoing, or changing the inclusion of a
segment or worker records a coalesced derivative-refresh intent inside the
backend mutation transaction. It does not depend on a browser timer, so closing
or navigating away immediately after an edit cannot strand stale derived data.
The request captures the latest annotation revision and coalesces a burst of
edits into one `annotation_derivatives` job. That worker stage rebuilds only
generated windows and feature artifacts. It does not run Threshold or Model
inference and does not materialize suggestion segments, so saved labels cannot
be overwritten as a side effect of editing.

If a normal processing pipeline is active, the refresh is recorded as
`deferred` and is promoted after that pipeline reaches a terminal state. A
revision changed during derivative processing invalidates the stale result and
queues the newest revision. Selecting **Suggestion** remains the explicit
action that can generate a fresh set of suggested labels.

Generated labels use the same durable handoff. Their complete segment set and
the deferred derivative intent commit together; the final Threshold or Model
job promotes that intent instead of relying on an in-process follow-up. If a
worker restarts immediately after materialization, recovery still rebuilds the
matching windows and features before export uses them.

Worker merge and split corrections use an immutable pose-artifact handoff as
well. A rewritten pose artifact receives a new version and the corresponding
SQLite mutation switches the video pointer in the same commit as its worker
rows and events. The old pose artifact remains authoritative until then, so an
interrupted correction cannot expose new pose IDs with an old worker list.

## Operations and retention

No external broker or new launcher command is required. Continue to start the
application with:

```powershell
uv run python -m backend.scripts.start_app
```

The SQLite outbox retains a bounded recent history by age and per-project event
count. Retention is a recovery optimization, not a correctness dependency:
expired cursors always receive `resync.required` and recover through the
snapshot endpoint.
