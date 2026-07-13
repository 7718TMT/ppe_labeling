# Final Specification: 3-Class Pose-Based Video Labeling Tool

## 1. Purpose

This document is the implementation source of truth for extending the existing labeling tool into a complete **labeling-only, human-in-the-loop annotation system** for industrial CCTV behavior data.

The tool supports exactly three annotation classes:

```text
others
running
falling
```

The same three classes are used for:

- human segment annotation,
- generated sliding-window labels,
- threshold-based label suggestions,
- externally supplied model-based label suggestions,
- exported ML and skeleton-sequence datasets.

The tool is strictly a labeling and dataset-preparation application. It must **not** train models, create train/validation/test splits, calculate model evaluation metrics, manage experiments, or perform automatic retraining.

The target pipeline is:

```text
Input videos
→ incremental YOLO-Pose processing
→ worker tracking
→ per-worker keypoint sequences
→ transformed pose and motion features
→ threshold-based suggestions OR external-model suggestions
→ human review and 3-class segment annotation
→ deterministic sliding-window generation
→ annotation/features/keypoint export
```

---

## 2. Scope Boundaries

### 2.1 Included

The final tool must provide:

1. Video import without a metadata CSV.
2. Incremental, per-video pose and tracking processing.
3. Immediate manual annotation after a video becomes tracking-ready.
4. Background feature extraction without blocking annotation.
5. Exactly three annotation classes.
6. Worker-track selection and basic track correction.
7. Frame-accurate segment annotation.
8. Automatic sliding-window generation.
9. Automatic extraction of the complete feature schema.
10. Threshold-based `falling` and `running` suggestions.
11. Inference-only suggestions from an externally trained compatible model.
12. A UI toggle between threshold suggestions and model suggestions.
13. Clear separation between suggestions and human ground truth.
14. Quality checks, exclusions, autosave, history, and crash recovery.
15. Reproducible exports for downstream ML or ST-GCN-style training outside this tool.

### 2.2 Explicitly excluded

The tool must not implement:

- model training,
- hyperparameter tuning,
- train/validation/test split management,
- leakage checking between training splits,
- model evaluation dashboards,
- model comparison,
- automatic retraining,
- active-learning training loops,
- experiment tracking,
- deployment of alert logic.

An already trained model may be loaded only to generate annotation suggestions.

---

## 3. Final Class Definitions

### 3.1 `others`

Includes every controlled behavior that is not running or falling:

- standing,
- walking,
- fast walking that remains controlled walking,
- crouching,
- bending,
- kneeling,
- sitting,
- repairing equipment,
- picking up an object,
- operating or inspecting a machine,
- standing up from a normal crouch,
- normal hand and body movement,
- a worker who has fully returned to a stable normal posture after recovery.

### 3.2 `running`

Includes active running, sprinting, and clearly running-like high-speed locomotion.

The segment begins when the worker clearly enters a running gait. It ends when the worker:

- returns to walking or standing,
- leaves the valid track,
- or begins a clear fall.

When running transitions into falling, the label changes to `falling` at the first clearly uncontrolled loss-of-balance frame.

### 3.3 `falling`

Includes:

- clear loss of balance,
- the body actively falling toward the floor,
- slipping and collapsing,
- lying on the floor after a fall,
- attempts to sit up or stand up after the fall while still near or in contact with the floor.

The segment begins at the first clearly uncontrolled fall-like frame. It ends when the worker has returned to a stable normal posture.

### 3.4 Window-label priority

For a mixed generated window:

```text
falling > running > others
```

This priority affects only auto-generated window labels. It must never overwrite human segment labels.

---

## 4. Workflow and Quality States

The following are workflow states, not action classes:

```text
unlabeled
partially_labeled
labeled
needs_review
approved
excluded
low_quality
```

Suggested exclusion reasons:

```text
bad_pose
missing_keypoints
id_switch
wrong_track
worker_too_small
track_too_short
ambiguous_motion
corrupted_video
duplicate_video
manual_exclusion
```

Use fields such as:

```text
include_in_export: true | false
quality_status: good | needs_review | low_quality | excluded
exclude_reason: nullable enum/string
```

Do not create extra action labels such as `ambiguous`, `bad_pose`, `lying`, or `recovery`.

---

## 5. High-Level Architecture

```text
Frontend labeling application
        │
        ▼
Application API
        ├── project and video management
        ├── processing queue management
        ├── track and annotation management
        ├── feature and suggestion management
        ├── sliding-window generation
        └── export management
        │
        ▼
Background workers
        ├── video probing/resampling
        ├── YOLO-Pose inference
        ├── tracking
        ├── feature extraction
        ├── threshold suggestion generation
        ├── external-model inference
        └── export generation
        │
        ▼
Persistent storage
        ├── SQLite project database
        ├── raw videos
        ├── pose/tracking cache
        ├── feature cache
        ├── threshold suggestions
        ├── model suggestions
        └── export artifacts
```

The UI must remain usable while background jobs are running.

---

## 6. Project Configuration

Each project stores a versioned configuration.

```yaml
class_map:
  others: 0
  running: 1
  falling: 2

video:
  canonical_fps: 24
  resample_to_canonical_fps: true

pose:
  model_name: yolo-pose-model-name
  model_version: model-file-hash-or-version
  detection_confidence: 0.25
  keypoint_confidence: 0.10

tracking:
  tracker: bytetrack
  tracker_config_version: v1

window:
  length_frames: 60
  stride_frames: 12
  final_period_frames: 24

window_labeling:
  falling_min_overlap_frames: 8
  falling_final_period_ratio: 0.50
  running_min_ratio: 0.50
  others_min_ratio: 0.70
  priority:
    - falling
    - running
    - others

quality:
  min_average_keypoint_confidence: 0.35
  max_missing_ankle_ratio: 0.40
  min_valid_frame_ratio: 0.70
  max_interpolation_gap_frames: 6

features:
  feature_schema_version: v1

suggestions:
  default_source: threshold
  threshold_profile_version: v1
  minimum_segment_frames: 6
  merge_gap_frames: 6

annotation:
  annotation_schema_version: v1
```

The project must also store:

- application version,
- pose model version,
- tracker version,
- feature extractor version,
- threshold profile version,
- external model metadata when loaded,
- export schema version,
- creation/update timestamps.

---

## 7. Video Import

Supported input methods:

- folder import,
- multi-file selection,
- drag-and-drop.

No metadata CSV is required.

Automatically extract:

- filename,
- relative path,
- file hash,
- original FPS,
- total frame count,
- duration,
- width and height,
- codec,
- file size,
- parent-folder group.


Detect exact duplicates using file hashes. Near-duplicate detection is optional.

---

## 8. Incremental Per-Video Processing

Each video is processed independently.

```text
imported
→ probed
→ pose_queued
→ pose_processing
→ pose_ready
→ tracking_processing
→ annotation_ready
→ feature_processing
→ feature_ready
→ threshold_suggestion_ready
→ model_suggestion_ready (optional)
```

### 8.1 Readiness levels

A video becomes manually annotatable as soon as pose and tracking complete:

```text
annotation_ready = pose_ready + tracking_ready
```

The user must not wait for feature extraction or suggestion generation.

Feature readiness is separate:

```text
feature_ready = Group A-E feature data available

- clear progress bar viewing so that user know the current processing progress
- clear status for available image.
```

### 8.2 Queue behavior

The queue must support:

- one job record per video and stage,
- batch enqueueing,
- configurable concurrency,
- pause/resume,
- cancel,
- retry,
- priority changes,
- persistent progress,
- failed-job logs,
- restart recovery.

Default priority:

1. video explicitly opened/requested by the user,
2. next videos in the annotation queue,
3. remaining imported videos,
4. stale or reprocessing jobs.

A UI batch may contain 5-10 videos, but backend jobs remain independently retryable per video.

---

## 9. FPS Normalization

The feature specification assumes:

```text
24 FPS
60 frames = 2.5 seconds
12 frames = 0.5 seconds
```

Normalize videos to a canonical 24 FPS processing timeline. Preserve:

- original FPS,
- canonical FPS,
- original-to-canonical frame mapping,
- canonical frame-to-timestamp mapping.

Annotations, tracks, features, suggestions, and windows use canonical frame indices.

---

## 10. YOLO-Pose and Tracking Output

For every person detection, store:

```text
frame_id
bbox = [x1, y1, x2, y2]
keypoints = [17, 2]
keypoint_scores = [17]
person_detection_confidence
```

Use standard COCO 17-keypoint order.

Use yolo26m-pose

For each worker track, store:

- track ID,
- start and end frame,
- valid frame count,
- gap count,
- average person confidence,
- average keypoint confidence,
- missing-joint ratios,
- quality status.

### Required track operations

- click a worker in the video to select its track,
- select a track from the sidebar,
- hide non-selected tracks,
- auto-select the longest track,
- merge fragmented tracks,
- split a track at the current frame,
- reassign a segment to another track,
- exclude a track.

Track edits invalidate only affected features, suggestions, and windows.

---

## 11. Dataset Browser

Each video row should show:

- video name,
- duration,
- processing stage,
- number of tracks,
- annotation status,
- quality status,
- threshold-suggestion availability,
- model-suggestion availability,
- last updated time.

Filters:

```text
unprocessed
processing
annotation_ready
unlabeled
partially_labeled
needs_review
approved
low_quality
excluded
failed
threshold_suggestions_ready
model_suggestions_ready
```

Batch actions:

- process selected videos,
- retry failed processing,
- assign an entire selected track/video as `others`, `running`, or `falling`,
- exclude or restore,
- approve,
- generate threshold suggestions,
- generate external-model suggestions when a compatible model is loaded.

---

## 12. Labeling Workspace

Recommended layout:

```text
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│ Breadcrumbs                                        Export Dataset   Batch Label ▼ (Model / Threshold)         │
├───────────────┬───────────────────────────────────────────────────────┬───────────────────────────────────────┤
│ Left Sidebar  │ Main Workspace                                        │ Right Sidebar                         │
│               │                                                       │                                       │
│ • Progress    │  Video Player + Pose Overlay                          │ • Active Tracks                       │
│ • Upload      │                                                       │ • Class Selection                     │
│ • Rename      ├───────────────────────────────────────────────────────┤ • Suggestions                         │
│ • Video       │ Multi-layer Timeline                                  │                                       │
│  Selection    │                                                       │                                       │
└───────────────┴───────────────────────────────────────────────────────┴───────────────────────────────────────┘
```

### 12.1 Player controls

- play/pause,
- previous/next frame,
- jump ±5 or ±10 frames,
- jump to frame,
- playback speed,
- loop selected segment,
- zoom,
- full screen,
- auto-center selected worker.

### 12.2 Overlay controls

- show/hide bbox,
- show/hide skeleton,
- show/hide track ID,
- show/hide confidence,
- selected track only,
- human labels,
- generated windows,
- quality warnings,
- active suggestion source.

---

## 13. Suggestion Source Toggle

The UI must contain a prominent segmented control:

```text
Suggestion source:  Off | Threshold | AI
```

### 13.1 Required behavior

- `Off`: show only human annotations and quality information.
- `Threshold`: display suggestions generated from configurable thresholds applied to transformed features.
- `AI`: display suggestions generated by the currently loaded external model.
- Only one suggestion source is shown as the primary overlay at a time.
- Switching the source must never alter human annotations.
- Threshold and model suggestions are cached separately.
- If no compatible model is loaded, `AI` is disabled with an explanatory tooltip.
- The selected toggle mode is remembered per user/session.

### 13.2 Visual distinction

Use:

- solid blocks for human labels,
- translucent blocks with a threshold icon for threshold suggestions,
- dashed/translucent blocks with a model icon for model suggestions.

### 13.3 Suggestion actions

For either source, the user can:

```text
accept
convert to editable segment
modify boundaries
change class
reject
hide
```

Accepting a suggestion creates or updates a human segment. The source suggestion remains stored for provenance but is never itself ground truth.

---

## 14. Segment Annotation

A segment contains:

```text
video_id
track_id
start_frame
end_frame
label
```

The label is exactly one of:

```text
others
running
falling
```

Required operations:

- set start and end,
- assign label,
- drag boundaries,
- split,
- merge adjacent same-label segments,
- delete,
- extend to track start/end,
- label the entire track,
- copy previous label,
- undo/redo,
- autosave.

Validation before approval:

- `start_frame <= end_frame`,
- inside video range,
- inside track lifespan,
- non-zero segment length,
- no conflicting overlaps,
- valid class only,
- optional full-track coverage.

The UI must highlight overlaps, gaps, and invalid ranges.

---

## 15. Keyboard Shortcuts

```text
Space         play/pause
Left          previous frame
Right         next frame
Shift+Left    back 10 frames
Shift+Right   forward 10 frames

I             set segment start
O             set segment end

1             others
2             running
3             falling

T             show threshold suggestions
M             show model suggestions
S             turn suggestions off

A             accept selected suggestion
R             reject selected suggestion
X             exclude selected segment/window
Enter         save
Ctrl+Z        undo
Ctrl+Y        redo
N             approve and open next video
```

Shortcuts should be configurable.

---

## 16. Timeline Layers

The timeline can contain:

1. human annotations,
2. active suggestions from the selected source,
3. generated sliding windows,
4. pose quality,
5. transformed feature curves,
6. current frame marker,
7. selected segment.

The timeline must support:

- clicking a suggestion to select it,
- dragging suggestion boundaries before acceptance,
- jumping to feature peaks,
- filtering to only `falling` or `running` suggestions.

---

## 17. Sliding Window Generation

Default window configuration:

```text
length = 60 frames
stride = 12 frames
final period = last 24 frames
```

For a 120-frame track:

```text
0-59
12-71
24-83
36-95
48-107
60-119
```

A window belongs to one video and one worker track only.

### 17.1 Human-label-to-window mapping

#### Falling

Assign `falling` when:

```text
falling overlap >= falling_min_overlap_frames
```

or:

```text
falling ratio in final 24 frames >= falling_final_period_ratio
```

#### Running

If not falling:

```text
running frames / valid labeled frames >= running_min_ratio
```

#### Others

If not falling or running:

```text
others frames / valid labeled frames >= others_min_ratio
```

#### Unresolved

```text
include_in_export = false
quality_status = needs_review
```

No fourth class is created.

Changing annotations, tracks, window configuration, or mapping thresholds marks affected windows and window features stale.

---

## 18. Raw and Window Feature Extraction

Annotators never enter or edit feature values manually.

Normalize spatial distances using:

```text
body_size = sqrt(bbox_width^2 + bbox_height^2)
```

Fallback order:

1. bbox diagonal,
2. bbox height,
3. torso length when reliable.

The system should preserve both raw feature values and transformed feature scores.

---

## 19. Group A: Posture Geometry

### 19.1 Torso angle

```text
S = average(left_shoulder, right_shoulder)
H = average(left_hip, right_hip)
v = S - H
angle = atan2(abs(v_y), abs(v_x)) in degrees
```

Outputs:

```text
torso_angle_mean
torso_angle_std
```

### 19.2 Head-hip compression

```text
abs(nose_y - hip_center_y) / bbox_height
```

Output:

```text
head_hip_compression_mean
```

### 19.3 Hip-ankle vertical difference

```text
abs(hip_center_y - ankle_midpoint_y) / body_size
```

Output:

```text
hip_ankle_vertical_diff_mean
```

### 19.4 Coalesced shape ratio

Preferred:

```text
(max(valid_x) - min(valid_x)) /
(max(valid_y) - min(valid_y))
```

Fallback:

```text
bbox_width / bbox_height
```

Outputs:

```text
skeleton_spread_ratio_mean
skeleton_spread_ratio_max
```

---

## 20. Group B: Locomotion and Dynamics

Ground point:

- midpoint of valid ankles,
- otherwise bbox bottom center.

Ground speed:

```text
distance(P_t, P_t-1) / (bbox_height * delta_time)
```

Outputs:

```text
ground_speed_mean
ground_speed_max
```

Scale speed:

```text
abs(bbox_height_t - bbox_height_t-1) /
(bbox_height_t * delta_time)
```

Output:

```text
scale_speed_mean
```

Combined speed:

```text
ground_speed + 0.45 * scale_speed
```

Outputs:

```text
combined_speed_mean
combined_speed_std
```

Body-center speed and acceleration:

```text
body_center = average(shoulder_center, hip_center)

body_speed =
distance(body_center_t, body_center_t-1) /
(body_size * delta_time)

body_acceleration =
abs(body_speed_t - body_speed_t-1) / delta_time
```

Outputs:

```text
body_speed_max
body_acceleration_max
```

---

## 21. Group C: 15-Step Decimated Time Series

For each 60-frame window, sample:

```text
t0, t4, t8, ..., t56
```

At each of 15 steps store:

```text
step_torso_angle_t{i}
step_compression_t{i}
step_spread_ratio_t{i}
step_combined_speed_t{i}
step_hip_ankle_t{i}
step_ground_speed_t{i}
step_scale_speed_t{i}
step_body_speed_t{i}
```

Total:

```text
15 × 8 = 120 features
```

For short internal gaps, interpolate between nearest valid points. Do not interpolate:

- gaps longer than the configured maximum,
- values outside the track lifespan,
- windows below the minimum valid-frame ratio.

Record provenance per step:

```text
observed
interpolated
missing
```

---

## 22. Group D: Final Posture and Stillness

Use the final 24 frames of each 60-frame window.

Outputs:

```text
final_lying_score
final_1s_body_speed_mean
final_1s_joint_motion_mean
final_1s_joint_motion_std
```

`final_lying_score` is derived from end-window posture and stillness. It is a feature and threshold signal, not ground truth.

---

## 23. Group E: Quality Features

Required:

```text
avg_keypoint_confidence
missing_ankle_ratio
```

Recommended:

```text
valid_frame_ratio
missing_hip_ratio
track_gap_count
skeleton_jump_score
```

These fields support quality filtering and suggestion confidence.

---

## 24. Transformed Feature Scores

Threshold suggestions must not apply thresholds directly to every raw feature with inconsistent ranges. The tool must transform selected raw features into normalized scores in `[0, 1]`.

Define:

```text
ramp(x, low, high) = clamp((x - low) / (high - low), 0, 1)
```

All values below are configurable defaults and must be editable in a Threshold Profile screen.

### 24.1 Fall-related transformed scores

#### Torso horizontal score

```text
torso_horizontal_score = 1 - ramp(torso_angle, 25°, 75°)
```

Interpretation:

- near 0: vertical torso,
- near 1: horizontal torso.

#### Compression score

```text
compression_score = 1 - ramp(head_hip_compression, 0.32, 0.85)
```

#### Flat hip-ankle score

```text
hip_ankle_flat_score = 1 - ramp(hip_ankle_vertical_diff, 0.28, 0.90)
```

#### Horizontal spread score

```text
spread_score = ramp(coalesced_shape_ratio, 0.80, 1.60)
```

#### Fall acceleration score

```text
fall_acceleration_score = ramp(body_acceleration, fall_accel_low, fall_accel_high)
```

The initial `fall_accel_low/high` must be configurable because the exact normalized range depends on pose noise and camera data.

#### Final stillness score

```text
final_stillness_score = 1 - ramp(final_1s_joint_motion_mean,
                                  stillness_motion_low,
                                  stillness_motion_high)
```

#### Final lying score

The existing `final_lying_score` should be normalized to `[0, 1]` and stored as:

```text
final_lying_score_norm
```

### 24.2 Running-related transformed scores

#### Combined locomotion score

```text
combined_locomotion_score = ramp(combined_speed,
                                  running_combined_speed_low,
                                  running_combined_speed_high)
```

#### Ground locomotion score

```text
ground_locomotion_score = ramp(ground_speed,
                                running_ground_speed_low,
                                running_ground_speed_high)
```

#### Body locomotion score

```text
body_locomotion_score = ramp(body_speed,
                              running_body_speed_low,
                              running_body_speed_high)
```

#### Sustained locomotion score

For a rolling interval, compute the fraction of valid frames/steps whose combined locomotion score exceeds the configured onset threshold:

```text
sustained_locomotion_score = count(score >= onset) / valid_count
```

#### Fall inhibition score

```text
fall_inhibition_score = max(torso_horizontal_score,
                            final_lying_score_norm,
                            spread_score)
```

A high fall-inhibition score suppresses running suggestions.

---

## 25. Threshold-Based Suggestion Engine

Threshold-based suggestions are annotation aids only. They do not create final labels automatically.

### 25.1 Input

The engine uses:

- per-frame transformed feature scores,
- rolling-window summaries,
- 60-frame window features,
- pose quality features.

### 25.2 Falling candidate score

Use separate transition and end-state evidence.

```text
fall_transition_score =
    w_accel      * fall_acceleration_score
  + w_rotation   * torso_rotation_change_score
  + w_spread     * spread_change_score
  + w_flatten    * hip_ankle_flat_change_score
```

```text
fall_state_score =
    w_torso      * torso_horizontal_score
  + w_spread     * spread_score
  + w_lying      * final_lying_score_norm
  + w_stillness  * final_stillness_score
```

Default weights may be supplied but must be configurable and versioned. The engine may also use logical rules instead of a weighted sum when configured.

Suggested default candidate conditions:

```text
Condition A:
fall_transition_score >= 0.65
for at least 2 consecutive sampled steps
AND fall_state_score >= 0.55 near the end

OR

Condition B:
final_lying_score_norm >= 0.75
for at least 2 consecutive windows
```

This allows suggestions when the actual transition is missed but the worker is clearly lying on the floor.

#### Falling segment start

Choose the earliest frame in the look-back range where at least two of the following begin changing in a fall-like direction:

- torso angle decreases sharply,
- body acceleration spikes,
- spread ratio increases,
- hip-ankle vertical difference decreases.

#### Falling segment end

End the suggestion only after:

```text
fall_state_score < fall_exit_threshold
for fall_exit_consecutive_frames
AND posture is stable
```

A worker who is still lying or recovering near the floor remains inside the suggested `falling` segment.

### 25.3 Running candidate score

```text
running_score =
    w_combined   * combined_locomotion_score
  + w_ground     * ground_locomotion_score
  + w_body       * body_locomotion_score
  + w_sustained  * sustained_locomotion_score
  - w_fall       * fall_inhibition_score
```

Suggested default entry condition:

```text
running_score >= 0.70
for at least 2 consecutive windows
AND fall_inhibition_score < 0.45
```

Suggested exit condition:

```text
running_score < 0.40
for at least 3 consecutive window positions
```

### 25.4 Quality gating

Do not generate a high-confidence threshold suggestion when:

```text
avg_keypoint_confidence < configured minimum
OR valid_frame_ratio < configured minimum
```

If ankle data is unreliable, reduce the contribution of `ground_locomotion_score` and rely more on body and scale motion.

### 25.5 Candidate merging

Merge adjacent or overlapping threshold candidates when:

- class is the same,
- gap is below `merge_gap_frames`,
- quality is acceptable.

Each stored threshold suggestion must include:

```text
video_id
track_id
start_frame
end_frame
suggested_label
confidence_score
threshold_profile_version
triggered_conditions
supporting_feature_values
quality_status
review_status
```

### 25.6 Threshold Profile UI

Provide a configuration panel for:

- raw-to-score transform low/high values,
- fall transition weights and thresholds,
- fall state weights and thresholds,
- running weights and thresholds,
- entry/exit consecutive counts,
- merge gap,
- quality gates.

Actions:

```text
save profile
clone profile
restore defaults
regenerate current video
regenerate selected videos
regenerate all stale videos
```

The UI must show which transformed scores crossed which thresholds.

---

## 26. External-Model Suggestion Engine

The labeling tool does not train models. It may load an externally trained model and run inference only.

### 26.1 Supported model packaging

A loaded model package must include:

```text
model artifact
model name/version
class_map
feature_schema_version
expected feature column order
window_length
stride
canonical_fps
optional probability calibration information
```

Possible artifact formats may include:

- `joblib`/pickle for trusted local Random Forest/XGBoost/LightGBM pipelines,
- ONNX when supported,
- another explicitly implemented inference adapter.

Never load untrusted pickle files without a warning because pickle execution is unsafe.

### 26.2 Compatibility validation

Before enabling `Model` mode, validate:

- exactly three classes are present,
- class names map to `others`, `running`, and `falling`,
- feature schema version matches,
- expected columns exist and are in the correct order,
- window length/stride match or a supported adapter exists,
- canonical FPS matches,
- model file can be loaded successfully.

If incompatible, disable the mode and display exact mismatches.

### 26.3 Model inference output

For each window store:

```text
others_probability
running_probability
falling_probability
predicted_label
confidence
external_model_id
```

### 26.4 Window-to-segment merging

Merge compatible predicted windows into editable suggested segments using configurable:

- minimum class probability,
- minimum consecutive windows,
- maximum merge gap,
- entry and exit hysteresis,
- priority `falling > running > others` where overlapping hazards occur.

### 26.5 Model suggestion provenance

For every suggested segment store:

```text
external_model_id
external_model_version
source_window_ids
class probabilities
merge configuration version
review_status
```

Loading a new external model must not overwrite old suggestions. Suggestions from each model version remain separately identifiable.

---

## 27. Suggestion Review Workflow

Suggestions are not annotations.

For both threshold and model sources, support:

```text
pending
accepted
modified
rejected
```

### Accept

Copy the suggestion into the human annotation layer.

### Modify

Create an editable human segment from the suggestion, then allow boundary/class changes.

### Reject

Keep the suggestion record and rejection status so it does not immediately reappear unchanged.

### Bulk actions

- accept selected high-confidence suggestions,
- reject selected suggestions,
- accept all suggestions for the active track,
- clear decisions for regeneration.

Bulk acceptance should require explicit confirmation.

---

## 28. Feature and Suggestion Inspector

The inspector should show:

- raw feature curves,
- transformed score curves,
- threshold lines,
- triggered conditions,
- threshold suggestion confidence,
- model class probabilities when Model mode is active,
- pose quality curve,
- 15-step feature heatmap.

Recommended graphs:

```text
torso angle / torso_horizontal_score
compression / compression_score
spread ratio / spread_score
combined speed / combined_locomotion_score
body acceleration / fall_acceleration_score
final lying score
running_score
fall_transition_score
fall_state_score
```

No manual feature editing is allowed.

---

## 29. Quality Control

Default QC rules:

```text
avg_keypoint_confidence < 0.35
→ needs_review

missing_ankle_ratio > 0.40
→ ankle/ground motion unreliable

valid_frame_ratio < 0.70
→ exclude window from normal export by default
```

Also detect:

- worker too small,
- excessive track gaps,
- skeleton jumps,
- bbox jumps,
- impossible limb changes,
- failed interpolation.

Quality thresholds are configurable and versioned.

---

## 30. Persistence Schema

Recommended SQLite tables follow.

### `projects`

```text
project_id
name
config_json
application_version
created_at
updated_at
```

### `videos`

```text
video_id
project_id
relative_path
file_hash
original_fps
canonical_fps
total_frames
width
height
folder_group
processing_status
annotation_status
quality_status
created_at
updated_at
```

### `tracks`

```text
track_pk
video_id
track_id
start_frame
end_frame
avg_keypoint_confidence
valid_frame_ratio
missing_ankle_ratio
quality_status
include_in_export
exclude_reason
```

### `segments`

```text
segment_id
video_id
track_id
start_frame
end_frame
label
annotation_version
created_by
created_at
updated_at
```

### `windows`

```text
window_id
video_id
track_id
start_frame
end_frame
label
label_reason
quality_score
quality_status
include_in_export
exclude_reason
window_config_version
feature_status
```

### `processing_jobs`

```text
job_id
video_id
stage
status
priority
progress
error_message
created_at
started_at
finished_at
retry_count
```

### `threshold_profiles`

```text
threshold_profile_id
name
version
config_json
created_at
updated_at
```

### `threshold_suggestions`

```text
suggestion_id
threshold_profile_id
video_id
track_id
start_frame
end_frame
suggested_label
confidence
triggered_conditions_json
supporting_features_json
quality_status
review_status
created_at
```

### `external_models`

This table stores only externally loaded inference packages, not trained models.

```text
external_model_id
name
version
artifact_path
artifact_hash
adapter_type
class_map_json
feature_schema_version
window_config_json
compatibility_status
metadata_json
loaded_at
```

### `model_window_predictions`

```text
prediction_id
external_model_id
window_id
others_probability
running_probability
falling_probability
predicted_label
confidence
created_at
```

### `model_suggestions`

```text
suggestion_id
external_model_id
video_id
track_id
start_frame
end_frame
suggested_label
confidence
source_window_ids_json
merge_config_json
review_status
created_at
```

### `annotation_history`

```text
history_id
entity_type
entity_id
operation
old_value_json
new_value_json
user_id
created_at
```

---

## 31. API Capabilities

The route naming may follow the existing codebase, but the following capabilities are required.

### Project

- create/open project,
- read/update configuration,
- read/update threshold profiles.

### Videos

- import/list/filter/read,
- exclude/restore,
- read processing and suggestion availability.

### Processing

- queue stages,
- pause/resume/cancel/retry,
- prioritize video,
- read progress and errors.

### Tracks

- list/read,
- merge,
- split,
- reassign segment,
- exclude/restore.

### Annotations

- create/update/delete segment,
- batch label,
- validate,
- approve,
- history,
- undo/redo.

### Windows and features

- generate/regenerate windows,
- extract/regenerate features,
- review/include/exclude windows,
- inspect raw/transformed features.

### Threshold suggestions

- generate for video/batch,
- list/read,
- accept/modify/reject,
- regenerate with selected profile.

### External model

- import/load/unload model package,
- validate compatibility,
- run inference on video/batch,
- list window predictions,
- list/accept/modify/reject merged suggestions.

There is intentionally no model-training API.

### Export

- validate export,
- create export,
- read status,
- retrieve generated files.

---

## 32. Cache and Invalidation

Dependency graph:

```text
video
→ pose
→ tracking
→ raw features
→ transformed features
→ threshold suggestions
→ windows/window features
→ model predictions/model suggestions
→ exports
```

Human segments depend on tracks but are not automatically deleted when upstream processing changes; instead they must be marked `needs_review` when track identity changes.

Examples:

```text
pose model changed
→ invalidate pose, tracking, features, both suggestion types, windows, exports

tracker changed
→ invalidate tracking/features/suggestions/windows/exports
→ mark affected annotations needs_review

threshold profile changed
→ invalidate threshold suggestions only

external model changed
→ preserve old model suggestions
→ generate a separate new suggestion set

segment changed
→ invalidate affected window labels and exports

window config changed
→ invalidate windows, window features, model predictions, and exports

feature schema changed
→ invalidate features, threshold suggestions, model compatibility, model suggestions, exports
```

Never overwrite raw videos or raw pose results silently.

---

## 33. Export Outputs

The tool exports labels and data for downstream use, but does not split or train them.

### 33.1 `annotations.jsonl`

```json
{
  "video_id": "video001",
  "track_id": 1,
  "start_frame": 43,
  "end_frame": 102,
  "label": "falling",
  "annotation_version": 3
}
```

### 33.2 `windows.parquet`

```text
window_id
video_id
track_id
start_frame
end_frame
label
quality_score
include_in_export
exclude_reason
```

### 33.3 `features.parquet`

Contains:

- stable IDs,
- Group A-E raw features,
- transformed feature scores,
- human-derived window label,
- quality fields,
- feature schema version.

### 33.4 `keypoint_windows.npz`

```text
keypoints: [N, 60, 17, 2]
keypoint_scores: [N, 60, 17]
bboxes: [N, 60, 4]
labels: [N]
```

### 33.5 Suggestion audit exports

Optional:

```text
threshold_suggestions.jsonl
model_suggestions.jsonl
suggestion_review_history.jsonl
```

These files must remain separate from human ground truth.

### 33.6 ST-GCN-compatible export

Optional adapter:

```text
keypoint: [M, T, V, 2]
keypoint_score: [M, T, V]
label
```

No train/validation/test split is created.

### 33.7 Export manifest

Include:

- class map,
- video hashes,
- pose model/version,
- tracker/version,
- canonical FPS,
- window length/stride,
- human-to-window label rules,
- feature schema version,
- transformed feature profile version,
- annotation schema/version,
- application version,
- export timestamp.

---

## 34. Information

The labeling UI should show:

- imported videos,
- processed videos,
- annotation-ready videos,
- labeled/approved/excluded videos,
- track count,
- segment count by three classes,
- generated window count by three classes,
- unresolved windows,
- low-quality windows,
- threshold suggestions pending/accepted/modified/rejected,
- model suggestions pending/accepted/modified/rejected,
- average pose quality,
- processing queue status.

Do not show training metrics, split distribution, or model evaluation.

---

## 35. Reliability and Recovery

Required:

- autosave after segment changes,
- persistent job queue,
- restart recovery,
- reopen last video/track/frame,
- retry failed jobs,
- annotation history,
- deterministic regeneration,
- preserve raw caches,
- atomic exports,
- export validation,
- no silent deletion of accepted human labels.

---

## 36. Performance Requirements

The tool must:

- make a video annotation-ready immediately after pose/tracking,
- allow annotation while other videos process,
- avoid repeated full-video decoding,
- use cached pose/overlay data,
- virtualize large video lists,
- load only the active track/window data,
- perform heavy tasks in background workers,
- generate threshold suggestions incrementally per video,
- run external-model inference incrementally per feature-ready video.

YOLO-Pose is expected to dominate compute cost. Feature transforms, threshold suggestions, and classical model inference should remain lightweight.

---

## 37. Final User Workflow

```text
1. Create or open a labeling project.
2. Import a folder/list of videos.
3. Probe and normalize videos automatically.
4. Process pose and tracking incrementally.
5. Open the first annotation-ready video while the rest continue processing.
6. Extract raw and transformed features in the background.
7. Choose suggestion source: Off, Threshold, or Model.
8. Review suggested falling/running segments when available.
9. Accept, modify, reject, or manually create segments.
10. Annotate using only others/running/falling.
11. Validate and approve the track/video.
12. Generate deterministic 60-frame windows with stride 12.
13. Review unresolved or low-quality windows when necessary.
14. Export annotations, keypoints, windows, and features.
```

---

## 38. Implementation Order for the Existing Tool

### Phase 1: Persistence and incremental processing

- project configuration,
- SQLite schema,
- video import/probing,
- per-video processing jobs,
- pose/tracking cache,
- annotation-ready state,
- pause/resume/retry/recovery.

### Phase 2: Complete manual labeling

- video workspace,
- track selection,
- three-class segment labels,
- shortcuts,
- validation,
- batch full-track labeling,
- track merge/split,
- autosave/history.

### Phase 3: Features and threshold suggestions

- Group A-E feature extraction,
- transformed feature scores,
- threshold profile management,
- falling/running candidate generation,
- timeline overlay,
- accept/modify/reject,
- threshold provenance inspector.

### Phase 4: External-model suggestions

- model package import,
- compatibility validation,
- inference-only adapter,
- per-window probability storage,
- window-to-segment merging,
- Model toggle mode,
- accept/modify/reject.

### Phase 5: Windows and exports

- human-label-to-window mapping,
- window review,
- quality filtering,
- JSONL/Parquet/NPZ export,
- optional ST-GCN adapter,
- manifest and export validation.

---

## 39. Acceptance Criteria

The final labeling-only implementation is complete when:

1. Videos import without metadata CSV.
2. Videos process independently in the background.
3. The first tracking-ready video can be annotated while other videos continue.
4. Pose/tracking outputs are cached and resumable.
5. Tracks can be selected, merged, split, and excluded.
6. Human annotation uses only `others`, `running`, and `falling`.
7. Annotation validation prevents conflicts and invalid ranges.
8. Group A-E raw features are extracted automatically.
9. Transformed feature scores in `[0,1]` are generated and inspectable.
10. Threshold-based falling and running suggestions are generated from configurable transformed-feature thresholds.
11. The UI provides `Off | Threshold | AI` suggestion-source toggle.
12. Threshold and model suggestions are visually and persistently separate.
13. An external compatible model can be loaded for inference without training inside the tool.
14. Incompatible external models are rejected with clear reasons.
15. Suggestions can be accepted, modified, or rejected.
16. Suggestions never overwrite human annotations automatically.
17. Sliding windows are generated deterministically at 60/12.
18. Low-quality and unresolved windows can be excluded with reasons.
19. Exports contain annotations, windows, features, keypoints, and a reproducibility manifest.
20. No model training, data split management, or evaluation workflow exists in the application.
21. Work and processing recover correctly after restart.
22. Upstream changes invalidate only affected downstream artifacts.
