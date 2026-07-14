# Pose Video Labeling User Guide

This guide is for annotators using the Pose module. The same application also
contains the PPE and Sign image-labeling modules.

Pose is a labeling-only workflow. It does not train models, split datasets, or
evaluate model performance. After processing an initially unlabeled video, the
selected Threshold or AI results are automatically added as editable ground-
truth segments. Remaining detected-track ranges are labeled `others`, so every
track has an initial complete label timeline. Suggestion provenance is retained
for audit.

## 1. Start the complete application

After the one-time dependency setup in the main README, run this command from
the repository root:

```powershell
uv run python -m backend.scripts.start_app
```

This starts the API, persistent video worker, and React frontend together. Open
`http://localhost:5173`.

The command requires ports `8000` and `5173` to be available. Press `Ctrl+C` in
the terminal to stop every service cleanly.

## 2. Open the Pose module

The home page has three modules:

- **PPE** for PPE image annotation;
- **Sign** for safety-sign image annotation;
- **Pose** for tracked behavior video annotation.

Select **Pose**, create a project if needed, and open its project card. Projects
keep their videos, annotations, processing state, and exports separate.

## 3. Import videos

Use either method in the left video browser:

1. Select **Import videos** and choose one or more files.
2. Drag video files onto the video browser.

No metadata CSV is required. Imported media is copied into project-owned
storage; the original file outside the project is not changed.

Each compact video card shows:

- a cached thumbnail or fallback preview;
- the video name;
- duration and canonical frame count;
- one simple processing status;
- a separate annotation status;
- a delete button.

Processing status is limited to:

```text
Unprocessed
Processing
Ready
Failed
```

Annotation status is shown separately as:

```text
Unlabeled
Labeled
Approved
```

The browser has two filters above the cards:

- **System processing** filters the background pipeline: Unprocessed has not
  started, Processing is queued or running, Ready can be annotated, and Failed
  needs retrying.
- **User labelling** filters annotation progress: Unlabeled has no human
  segments, Labeled segments are editable ground truth, and Approved has been
  finalized for export.

Leave either filter on **All** to ignore it. If both filters have a selection,
only videos that match both states are shown. The selected video has a teal
border and highlight.

Use **Order** to sort the filtered list by recently updated, video name,
duration, frame count, system processing, or user labelling. Its arrow changes
between ascending and descending order. The default is recently updated with
the newest video first.

## 4. Process a video

The top toolbar has one split **Suggestions** control:

```text
[ Suggestion ] [ v ]
```

or:

```text
[ Suggestion ] [ v ]
```

1. Select the arrow only when you want to change the displayed source.
2. Choose **Threshold**, **AI**, or **Off**.
3. With Threshold or AI selected, select the main button to generate
   suggestions for the current video with that method.

The selected source is remembered for the project. It also determines the
method automatically queued for videos imported next: Threshold queues the
threshold workflow and AI queues the compatible model workflow. **Off** hides
suggestions and disables generation; imports use Threshold while Off is active.
The main button is disabled while the selected video already has active
processing.

When processing finishes, the generated segments appear in both the timeline's
human-label bar and the segment group. Review, edit, delete, or approve them as
needed; they are included as ground-truth annotations even before review.

- **Threshold** generates falling and running suggestions from motion rules.
- **AI** uses the compatible pretrained model configured by the application
  administrator.

If Model is unavailable, its option is disabled with a short explanation. Model
paths, feature schemas, thresholds, classifier settings, and ML parameters are
not exposed to annotators.

The processing queue uses plain stage names such as:

```text
Preparing video
Detecting and tracking workers
Extracting motion features
Generating suggestions
```

Use its controls to pause, resume, cancel, or retry a failed job. Processing one
video does not block labeling another ready video.

For fast falls and rotations, the worker uses a heavier BoT-SORT profile with a
dedicated appearance encoder. It keeps an interrupted worker track alive for up
to three seconds and compares 512-value appearance embeddings before it creates
a new ID. A reprocessed video records this profile as
`botsort-dedicated-reid-v3`. This improves continuity but does not replace
reviewer track-merge and split controls when people overlap or leave the camera
view.

## 5. Understand the workspace

The workspace has four areas:

- **Left:** video cards, import, filters, deletion, and processing queue.
- **Center:** video, pose overlay, playback controls, and frame number.
- **Timeline:** human labels, active suggestions, windows, and current frame.
- **Right:** only **Annotate**, **Suggestions**, and **Details**.

Use the panel buttons in the toolbar to collapse the left or right side. On
smaller displays the panels start collapsed so the player remains usable.

## 6. Play, scrub, and navigate frames

Player controls support:

- play and pause;
- backward or forward 10 frames;
- an exact canonical frame number;
- 0.25x, 0.5x, 1x, or 2x playback speed;
- looping the selected segment, or the full video when no segment is selected;
- bounding-box visibility;
- full screen.

The media plays to its actual end. Missing pose data does not stop playback.
The video, skeleton, worker boxes, track IDs, frame number, and timeline cursor
remain synchronized. You can scrub before, during, or after playback.

Switching from video A to B and back reloads the media cleanly while keeping the
saved annotations and cached poses for each video.

Use **Timeline zoom** for long videos and scroll horizontally after zooming.

## 7. Select and correct a worker track

Select a worker by either:

- clicking its box in the video; or
- selecting **Worker N** in the **Annotate** tab.

The longest track is selected automatically when appropriate. Available tools:

- **Show selected worker only** hides other overlays;
- **Merge** joins a fragmented track into the selected track;
- **Split here** splits at the current frame;
- **Exclude** omits a bad track from normal export;
- **Restore** includes it again.

Track edits preserve human segments. Affected segments are marked for review,
and only dependent pose-derived data is invalidated.

## 8. Create and edit human segments

Human annotation uses exactly three classes:

```text
others
running
falling
```

To create a segment:

1. Select a worker track.
2. Select the **Create Segment** card below that track's segment cards.
3. Move to the first frame and press `I`, or type it in **Start**.
4. Move to the last frame and press `O`, or type it in **End**.
5. Select **Others**, **Running**, or **Falling**.
6. Select **Add segment** or press `Enter`.

Human segments use solid timeline blocks and matching cards below the worker
track. Select a timeline block or its segment card to reveal its editor below
the card list; edit its frames or class, drag its boundary sliders, and select
**Modify segment**.

Select the same segment card, or the active **Create Segment** card, again to
deselect it and return to full-video mode. With no segment selected, the
**Loop** player control repeats the entire video; with a segment selected, it
repeats only that segment.

Edits to an existing segment autosave after a short pause. The toolbar reports
**Unsaved changes**, **Saving**, then **Saved**. If autosave fails, keep the
video open, resolve the displayed conflict or connection error, and select
**Modify segment** to retry; the unsaved draft remains visible meanwhile.

Each selected segment card provides **Split at frame** and **Delete**. Undo and
Redo remain available in the toolbar.

The application rejects out-of-range frames, track-lifespan violations,
conflicting same-track overlaps, invalid classes, and stale revision writes.
Different workers may have overlapping segments.

## 9. Apply the class definitions consistently

### Falling

Start `falling` at the first clear uncontrolled loss-of-balance frame. Lying on
the floor after a fall remains `falling`. Attempts to recover remain `falling`
until the worker returns to a stable normal posture. If running becomes a fall,
switch to `falling` when the clear loss of balance begins.

### Running

Use `running` for active running, sprinting, or a clearly running gait. End it
when the worker returns to walking or standing, leaves the valid track, or
begins falling.

### Others

Use `others` for all normal work behavior that is not running or falling,
including standing, walking, bending, crouching, kneeling, sitting, equipment
work, and stable recovery after a fall.

## 10. Review suggestions

Open **Suggestions**. The display toggle is:

```text
Off | Threshold | AI
```

- **Off** hides suggestions and shows human labels only.
- **Threshold** shows the active threshold suggestion set.
- **AI** shows suggestions from the configured external model.

Threshold suggestions use translucent blocks with solid outlines. AI
suggestions use dashed outlines. Neither style can be confused with solid human
labels.

Select a pending suggestion, then choose:

- **Accept** to copy it into the human annotation layer unchanged;
- **Modify** to create a human segment with the edited frames or class;
- **Reject** to retain an auditable rejection without creating a label.

Regenerating either suggestion source preserves all manual labels and keeps the
two suggestion sources separate.

## 11. Use Details, window review, and export

The **Details** tab shows essential video and selected-worker information plus
overlay controls. It contains optional collapsible sections:

- **Window review** includes or excludes deterministic 60-frame windows with
  stride 12;
- **Motion details** shows generated read-only feature and quality information;
- **Export dataset** validates and queues an atomic export. When the background
  job finishes, the browser automatically downloads one ZIP file; use
  **Download ZIP** if the browser blocked the automatic download.

Unresolved or low-quality windows do not create a fourth class. Mixed window
priority is `falling > running > others`.

Exports can contain:

```text
annotations.jsonl
keypoint_windows.npz
manifest.json
```

This compact export preserves the labelled pose windows and reproducibility
metadata needed for training. It does not create train, validation, or test
splits.

## 12. Complete a video

Resolve invalid or review-required segments, then select **Complete & Next**.
The application validates the video, records approval, and opens the next
available video. Editing a completed video invalidates its prior approval so it
can be reviewed again.

## 13. Delete a video

1. Select the trash button on the video card. It does not open the video.
2. Confirm the dialog containing the exact video name.
3. Wait for the success message.

Deletion removes the project's owned media copy, thumbnail, pose/tracking
caches, features, suggestions, annotations, windows, and processing jobs for
that video. It does not delete an external source file and does not affect any
other video. The next available video is selected automatically.

## 14. Use built-in Help

Select **Help** in the Pose toolbar at any time. The panel explains the basic
workflow, class boundaries, playback, shortcuts, suggestions, and deletion. It
is searchable, scrollable, dismissible with `Escape`, and does not interrupt
saved work.

## 15. Keyboard shortcuts

Shortcuts do not run while typing in an input, select, textarea, or editable
control. Hold `Alt` to show a temporary on-screen reference; release it to
close the guide.

| Shortcut | Action |
| --- | --- |
| `Space` | Play or pause |
| `Left` / `Right` | Previous or next frame |
| `Shift+Left` / `Shift+Right` | Move 10 frames |
| `I` / `O` | Set segment start or end |
| `1` | Select `others` |
| `2` | Select `running` |
| `3` | Select `falling` |
| `T` | Select Threshold for the Suggestion button |
| `M` | Select AI for the Suggestion button when available |
| `S` | Turn automatic suggestion generation off |
| `Esc` | Leave the selected segment and return to full-video mode |
| `Delete` | Delete the selected segment |
| `X` | Exclude or restore the selected segment |
| `Enter` | Create or update a segment |
| `Ctrl+Z` / `Ctrl+Y` | Undo or redo |
| `N` | Complete and open the next video |

## 16. Recovery and troubleshooting

### Processing does not start

- Confirm the unified launcher is still running.
- Confirm `weights/pose.pt` exists.
- Retry the failed queue item.
- If Model is disabled, ask an administrator to configure a compatible model.

### A video will not play

- Select another video and return to force a clean media reload.
- Confirm the imported source codec is supported by the local browser.
- Reimport a corrupted video; missing keypoints alone do not prevent playback.

### A job was interrupted

Jobs and progress are stored in SQLite. Restart the unified launcher. Stale
running jobs return safely to the queue and keep their selected suggestion mode.

### Approval fails

Check for overlaps, invalid ranges, review-required segments, or a video without
human annotation.

For storage, migration, trusted-model security, worker administration, and
manual service commands, see [`docs/operations.md`](operations.md).
