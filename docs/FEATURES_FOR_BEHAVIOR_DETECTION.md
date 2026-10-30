# Behavior feature reference: schema v1

This document describes the implemented extractor, not a proposed training
blueprint. The source of truth is
[`video_features.py`](../backend/app/services/video_features.py), especially
`feature_columns()` and `extract_window_features()`. Window orchestration is in
[`video_feature_service.py`](../backend/app/services/video_feature_service.py).

The extractor returns **143 raw features**: A (6), B (7), C (120), D (4), E (6).
The legacy `behavior_preprocess_v1` input has **141 columns** after dropping
`valid_frame_ratio` and `track_gap_count`; it is not the raw extraction schema.
Classes are `0=others`, `1=running`, `2=falling`. Features do not determine ground
truth by themselves. No accuracy or validated class-boundary claim is made here.

## Windows, ordering and notation

- Canonical FPS is 24. Extraction requires exactly 60 frames per worker track
  (2.5 seconds); the default window stride is 12 frames (0.5 seconds). Window
  generation follows project configuration and does not pad short tracks.
- Local indices are 0-59. The final period is local frames 36-59 (24 frames).
- Column order is `feature_columns()`: A, B, C, D, E, in the orders below.
  Do not infer feature order from JSON key order.
- W and H are nonnegative bounding-box width and height in pixels. S is its
  diagonal, falling back to height, torso length, then 1 when preceding scales
  are zero. These are image-space scales, not calibrated physical dimensions.
- A keypoint is usable at confidence >= the configured threshold (default 0.10).
  Shoulder, hip and ankle midpoints require both associated keypoints. Body
  center is the mean of shoulder/hip midpoints, without a bbox-center fallback.
- Mean/std ignore missing and nonfinite values and return 0 when none remain.
  Std uses population standard deviation (`pstdev`). Maxima ignore None and
  default to 0 for empty input. Normal inputs have finite pixel coordinates
  and 17 keypoint confidence values in [0,1].

## Frame geometry and motion

Torso angle is `degrees(atan2(abs(shoulder_y-hip_y), abs(shoulder_x-hip_x)))`.
Head-hip compression is `abs(nose_y-hip_y)/H`. Hip-ankle separation is
`abs(hip_y-ankle_y)/S`. Neither ratio is explicitly clipped to 1.

Spread is the x-range divided by y-range of keypoints above the confidence
threshold. It requires at least two usable points and nonzero y-range;
otherwise use W/H, or 0 when H is zero. An entirely missing frame has missing
geometry, rather than a bbox fallback.

For adjacent frames t-1 and t, dt=1/24:

| Metric | Definition | Unit |
|---|---|---|
| `ground_speed` | Euclidean ankle-midpoint displacement / `(H_t * dt)`; use bbox bottom-center when the ankle pair is unavailable | box heights/second |
| `scale_speed` | `abs(H_t-H_(t-1))/(H_t * dt)` | 1/second |
| `combined_speed` | `ground_speed + 0.45 * scale_speed`; an unavailable term contributes 0 if the other is available | normalized rate, 1/second |
| `body_speed` | Euclidean body-center displacement / `(S_t * dt)` | body scales/second |

Motion requires the relevant adjacent observations and nonzero denominator.
There is no cross-gap displacement calculation. Frame 0 has no predecessor
inside the window, so its motion metrics remain missing. Interpolation follows
motion calculation.

## Group A: posture summaries (6)

Summaries use the full metric arrays after eligible interpolation.

| Column, in order | Definition | Unit / range |
|---|---|---|
| `torso_angle_mean` | Mean torso angle | degrees, [0,90] |
| `torso_angle_std` | Population std of torso angle | degrees |
| `head_hip_compression_mean` | Mean head-hip compression | nonnegative ratio; no upper clamp |
| `hip_ankle_vertical_diff_mean` | Mean hip-ankle separation using S | nonnegative ratio; no upper clamp |
| `skeleton_spread_ratio_mean` | Mean skeleton/bbox spread | nonnegative ratio |
| `skeleton_spread_ratio_max` | Maximum skeleton/bbox spread | nonnegative ratio |

## Group B: motion summaries (7)

| Column, in order | Definition | Unit |
|---|---|---|
| `ground_speed_mean` | Mean ground speed | box heights/second |
| `ground_speed_max` | Maximum ground speed | box heights/second |
| `scale_speed_mean` | Mean scale speed | 1/second |
| `combined_speed_mean` | Mean combined speed | normalized rate, 1/second |
| `combined_speed_std` | Population std of combined speed | normalized rate, 1/second |
| `body_speed_max` | Maximum body-center speed | body scales/second |
| `body_acceleration_max` | Maximum `abs(body_speed_t-body_speed_(t-1))*24` across adjacent nonmissing interpolated speeds | body scales/second squared |

Acceleration is the magnitude of a scalar speed difference, not signed vertical
acceleration or physical acceleration in meters/second squared.

## Group C: sampled time series (120)

Sample local frames `0,4,8,...,56`, yielding 15 steps. At each step i, append
these eight columns in order before moving to i+1:

| Column pattern | Frame metric |
|---|---|
| `step_torso_angle_t{i}` | torso angle |
| `step_compression_t{i}` | head-hip compression |
| `step_spread_ratio_t{i}` | skeleton/bbox spread |
| `step_combined_speed_t{i}` | combined speed |
| `step_hip_ankle_t{i}` | hip-ankle separation |
| `step_ground_speed_t{i}` | ground speed |
| `step_scale_speed_t{i}` | scale speed |
| `step_body_speed_t{i}` | body speed |

Units match the metric definitions. Missing sampled values become 0; provenance
remains `missing`, distinguishing these from observed zeros. Motion is computed
at 24 FPS before sampling at 6 steps/second. Decimation does not itself provide
an anti-alias or smoothing filter; no such filter is applied at this stage.

## Group D: final-period posture and motion (4)

Define `ramp(x,lo,hi)=clip((x-lo)/(hi-lo),0,1)`. T is mean torso angle over
frames 36-59, R is mean spread there, and J is mean joint motion defined below.

| Column, in order | Definition | Unit / range |
|---|---|---|
| `final_lying_score` | Mean of `1-ramp(T,25,75)`, `ramp(R,0.8,1.6)`, `1-ramp(J,0.01,0.20)` | score, [0,1] |
| `final_1s_body_speed_mean` | Mean interpolated body speed in frames 36-59 | body scales/second |
| `final_1s_joint_motion_mean` | Mean joint motion for eligible adjacent pairs wholly inside frames 36-59 | body scales/frame pair |
| `final_1s_joint_motion_std` | Population std of that joint motion | body scales/frame pair |

Joint motion uses each frame's usable-joint list in original keypoint order.
An adjacent pair contributes only when both lists are nonempty and have equal
lengths. Pair the lists positionally, average Euclidean displacement and divide
by `max(S_t,1)`. There are at most 23 pairs. The implementation does not multiply
by FPS or interpolate these joint lists. Equal lengths do not guarantee matching
joint IDs when different joints are hidden; this is a current limitation.

Raw `final_lying_score` uses the fixed ranges above. It is a heuristic score,
not a calibrated probability. Missing summaries default to 0; the score alone
is not evidence of a valid lying pose.

## Group E: quality and diagnostics (6)

These values use original observations, before metric interpolation.

| Column, in order | Definition | Unit / range |
|---|---|---|
| `avg_keypoint_confidence` | Mean of all available scores in observed frames, including below-threshold scores; missing frames add no zero scores | confidence, [0,1] for valid inputs |
| `missing_ankle_ratio` | Fraction of all 60 frames that are missing or have either ankle below threshold | ratio, [0,1] |
| `valid_frame_ratio` | Number of non-None frame observations / 60; does not require a usable skeleton | ratio, [0,1] |
| `missing_hip_ratio` | Fraction of all 60 frames that are missing or have either hip below threshold | ratio, [0,1] |
| `track_gap_count` | Number of internal missing runs between observed indices; leading/trailing missing frames do not count | count stored as float |
| `skeleton_jump_score` | Maximum adjacent observed body-center displacement / `max(S_t,1)` | body scales/frame pair |

Diagnostics do not guarantee that a trained classifier will reject poor poses.

## Missing data and quality status

Linear interpolation applies independently to each of the eight metric arrays,
on the full 60-frame sequence before summary/sampling. Fill a missing run only
when its length is at most the configured maximum (default 6 frames) and valid
metric values exist at both ends. Leading, trailing and longer gaps remain
missing; there is no extrapolation.

Sampled provenance is `observed`, `interpolated` or `missing`. Quality counts
`observed_steps`, `interpolated_steps`, `missing_steps` count the 120 sampled
metric entries, not the 15 time indices.

Extractor status is `good` when observed-frame ratio >= `min_valid_frame_ratio`
(default 0.70), otherwise `low_quality`. It does not directly check average
confidence, missing ankles or jump score for that status. Window generation
separately checks track-level confidence and valid-frame ratio; feature
extraction updates stored window quality from its returned status and excludes
low-quality windows. Threshold suggestions separately check confidence and
frame-ratio thresholds. These stage-specific rules mean `good` is not complete
pose-quality validation.

## Raw features, threshold scores and model preprocessing

The feature cache stores `raw`, sampled `provenance`, `quality`, and a separate
`transformed` dictionary from `transform_features(raw, profile)`. Those threshold
scores use profile ramps/weights for heuristic suggestions; they are not extra
columns in the 143-feature raw model contract.

Model preprocessing and compatibility are implemented in
[`video_model_service.py`](../backend/app/services/video_model_service.py):

- `raw`: all 143 columns in `feature_columns()` order, without legacy transforms.
- `behavior_preprocess_v1`: remove `valid_frame_ratio` and `track_gap_count` while
  preserving order (141 columns). Apply `sqrt(max(0,x))` to `ground_speed_mean`,
  `ground_speed_max`, `combined_speed_mean`, `combined_speed_std`,
  `body_acceleration_max`. Apply `log1p(log1p(max(0,x)))` to
  `skeleton_spread_ratio_mean` and `skeleton_spread_ratio_max`. Other retained
  values are unchanged.

The model manifest must match preprocessing, feature order, class map and
window contract. See [configuration](CONFIGURATION.md) and
[data export](DATA_EXPORT.md). The compact training export contains labeled pose
windows, not an automatically prepared 143-column feature training table.
