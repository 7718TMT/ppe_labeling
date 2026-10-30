# User guide

Use this guide after [installing and starting the app](../README.md#install).
Choose **PPE**, **Sign** or **Behavior**, then **Labeling** to edit annotations
or **Inference** to inspect model predictions. Review AI labels before approval.
Terminal setup differs by OS; use the labeled commands in README. Browser
shortcuts use **Ctrl on Windows/Linux** and **Cmd on macOS** where shown as
Ctrl/Cmd. **Alt** is **Option** on Mac; terminal stop remains Ctrl+C on all OSes.

- [PPE and Sign labeling](#ppe-and-sign-labeling)
- [Behavior labeling](#behavior-labeling)
- [Inference](#inference)
- [Behavior shortcuts](#behavior-shortcuts)
- [Help and recovery](#help-and-recovery)

## PPE and Sign labeling

1. Select **Upload Images**, then choose an image from the list.
2. Choose a class in the properties panel and draw its box. Adjust boxes,
   correct classes and delete incorrect detections.
3. Optionally select **AI Current**. Check missed objects, extra boxes and class
   assignments. **AI Batch Label** replaces saved labels across the task; use
   it before manual review or back up existing work first.
4. Wait for **Saved**. Move to another image and return to verify the result.
   Review the whole image, then select **Approve Current Image**. Recheck
   approval after subsequent edits.
5. Select **Export Dataset**. Unapproved images can be included after
   confirmation. Check empty label files before treating them as negative samples.

Class names come from the installation's configuration. The default mappings
and file formats are in [Data export](DATA_EXPORT.md#ppe-and-sign-images).
Deleting an image also removes its labels and visualizations. Sequential rename
changes dataset filenames; back up before either operation.

## Behavior labeling

Open **Behavior > Labeling**, create a named project or open an existing one.
The workspace has a video browser/queue on the left, player and timeline in the
center, and **Annotate**/**Details** on the right. Toolbar panel buttons collapse
the sidebars; on small screens they may start collapsed.

### Import and find videos

- Select **Import videos** or drag files into the video browser. No metadata CSV
  is needed. Imports copy media into the project and leave external originals intact.
- Videos need at least **60 canonical frames**. Shorter uploads are rejected.
- Cards show processing status (**Unprocessed**, **Processing**, **Ready**,
  **Failed**) separately from annotation status (**Unlabeled**, **Labeled**,
  **Approved**). Generated labels can appear as Labeled before human review.
- Use **Search video names**, **System processing** and **User labelling** to
  narrow the list. Filters combine; **All** clears that filter. **Order** and
  its arrow control sorting; the default is most recently updated first.
- **Rename**, beside Import, renames project videos using a prefix and sequence,
  such as `fall_batch_00001`, while retaining extensions.

### Process and generate suggestions

1. Open the arrow on **Suggestion** and choose **Threshold**, **AI** or **Off**.
2. Select the main button to generate labels for the current video. If labels
   already exist, cancel to keep them or confirm to replace them.
3. Wait for **Ready**. Use the queue controls to pause, resume, cancel or retry.
   You can label another ready video while processing continues.
4. Review the generated timeline. Outputs are saved as editable segments with
   source provenance; there is no separate accept/reject step. Initially unlabeled
   detected-track ranges are filled with `others` where needed.

Threshold uses motion rules; AI uses the compatible model supplied by the
administrator. An unavailable AI option displays an explanation.
The source is remembered for the project and applies to later imports.
**Off** disables generation from the control without deleting existing labels;
imports still use Threshold while Off is selected. The main button is disabled
while the video has active processing.

Each video becomes Ready when its own processing finishes. The queue also shows
batch progress. Manual edits refresh derived data in the background without
creating new suggestions or replacing saved labels.

### Trim a video

Select the **scissors** beside fullscreen. Drag the two trim handles; click the
preview strip to move the playhead. **Preview range** loops the selected range.
Keep at least 60 frames. Use Undo/Redo for handle changes or **Reset** to start over.

- **Save copy** asks for a name; blank uses `<name>_copy.mp4`. The source remains.
- **Replace video** requires confirmation and replaces the current media. It
  resets processing, pose, suggestions, approval and history.

Both actions clip overlapping labels to the kept range and shift frame numbers
to start at zero. Saved trims are re-encoded MP4 files. Retained labels remain;
matching pose data is reused when available, otherwise processing is queued.
Later suggestions do not automatically overwrite retained labels.

### Navigate and correct workers

Use the player to play/pause, step 10 frames, enter an exact frame, change speed
(0.25x to 2x), loop, toggle boxes or enter fullscreen. Missing poses do not stop
video playback. **Timeline zoom** and horizontal scrolling help with long videos.
Loop repeats the selected segment, or the whole video when none is selected.

Select a worker's box or **Worker N** in Annotate. The longest track may be
selected automatically. Use:

- **Show selected worker only** to hide other overlays;
- **Merge** to join a fragmented track into the selected one;
- **Split here** to split at the current frame;
- **Exclude** to omit a bad track from normal export, or **Restore** to include it.

Track edits preserve segments and refresh dependent data; they do not generate
new suggestions. Review worker identity when people overlap or leave the view.

### Create and edit segments

1. Select a worker, then **Create Segment** below its cards.
2. Set the first frame with `I` or **Start**, and the last with `O` or **End**.
3. Choose **Others**, **Running** or **Falling**.
4. Select **Add segment** or press `Enter`.

Select a timeline block or segment card to edit it. Change class/frames or drag
its boundary sliders; use **Modify segment** to save explicitly. Existing segment
edits also autosave after a pause. Wait for **Saved**. If saving fails, keep the
video open, resolve the displayed error, then retry **Modify segment**.

Select the active card again to deselect it and return to full-video mode.
Segment cards offer **Split**, **Expand** and **Delete**. Use checkboxes or
Ctrl/Cmd-click for group selection; the card border identifies the editor's active
segment, independently of checkbox selection. Undo/Redo remain available.

Frames must stay within the video and worker lifespan. Conflicting segments
for one worker are rejected; different workers may overlap in time.

### Apply classes consistently

| Class | Labeling rule |
|---|---|
| Falling | Start at clear uncontrolled loss of balance. Include lying after the fall and recovery attempts until a stable normal posture returns. If running becomes a fall, switch at loss of balance. |
| Running | Active running, sprinting or a clear running gait. End at walking/standing, the track boundary or the start of a fall. |
| Others | Normal behavior outside those classes: standing, walking, bending, crouching, kneeling, sitting, equipment work and stable recovery. |

### Approve and export

1. Resolve invalid segments and review all generated labels.
2. Select **Complete & Next** to validate, approve and move to the next video.
   Later edits clear approval. The inspector's **Approval progress** tracks completion.
3. Open **Details** for video/worker information and overlay controls. Use
   **Export**, review validation errors/warnings and wait for the background job.
4. Download starts automatically on completion; use **Download ZIP** if blocked.

Only approved videos selected for export contribute. See
[Data export](DATA_EXPORT.md#behavior-video-samples) for inclusion rules, class
IDs and payload formats. An export is not a workspace backup.

### Delete videos, workers or segments

Use a video's trash button, or select cards with checkboxes/Ctrl/Cmd-click and
choose **Delete selected**. Delete/Backspace acts on the most recently selected
card type. Confirm video deletion and wait for success.

Deleting a video removes its project-owned media and associated work, not the
external original. Deleting a worker also removes its segments; deleting a
segment leaves the worker. Back up work before deletion.

## Inference

Inference results are separate from editable labeling workspaces.

**PPE/Sign:** open Inference, upload images or videos and select a result to view
boxes/classes. Use media filters to narrow the list. Delete removes the stored
inference item; it does not edit the labeling dataset.

**Behavior:** upload videos and wait for processing. Select a worker, raw window
or event to jump to its time. The inspector shows pose-quality warnings, event
counts and raw window confidence separately from smoothed events. The timeline
shows falling/running events and gray `others` ranges for uncovered track time.
Click a preview or event to navigate. Events cannot be moved or resized.
Fullscreen expands the player, controls and timeline; press Esc to leave.
Use the video card's trash button to remove a test video and its stored results.

## Behavior shortcuts

Shortcuts are inactive while typing. Hold **Alt** for the temporary reference;
select **Help** for searchable, scrollable guidance and Esc to close it.

| Shortcut | Action |
|---|---|
| Space | Play/pause |
| Left / Right | Previous/next frame |
| Shift+Left / Shift+Right | Move 10 frames |
| I / O | Set segment start/end |
| 1 / 2 / 3 | Others / Running / Falling |
| T / M / S | Select Threshold / AI / Off |
| Esc | Leave fullscreen or deselect the segment |
| Ctrl/Cmd-click or checkbox | Select multiple cards |
| Delete / Backspace | Delete the most recently selected card group |
| X | Exclude/restore segment |
| Enter | Add/update segment |
| Ctrl/Cmd+Z / Ctrl/Cmd+Y | Undo/redo (this app uses Y for redo, including on macOS) |

## Help and recovery

| Problem | What to do |
|---|---|
| Processing failed | Read the queue error and retry. If AI is unavailable, ask the administrator to check the model. |
| Video will not play | Select another video and return. Check browser codec support; reimport corrupt media. |
| Approval fails | Resolve overlaps, invalid ranges and review-required segments; ensure annotations exist. |
| Saving fails | Keep the draft open, resolve the shown error and retry saving. |

For model, CUDA, connection or worker failures, use
[operator troubleshooting](OPERATIONS.md#troubleshooting). For a full backup,
use [backup and restore](OPERATIONS.md#handover-backup-and-restore). Report the
module/project, filename, action and error message; preserve affected files.
