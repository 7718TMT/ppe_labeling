# Feature Engineering Blueprint: 3-Class Behavior Classification
This document provides a consolidated list of engineered features required to train a machine learning model (e.g., Random Forest, XGBoost, or LightGBM) to classify sliding-window worker trajectories into three target classes:
* **`falling`**: Falling motion, collapses, and lying on the floor.
* **`running`**: Stable high-speed movement.
* **`others`**: Aggregated class for normal stationary states, walking, bending, crouching, and kneeling.

---

## 1. Sliding Window Configuration
All features are computed over a sliding temporal window extracted per worker track ID:
* **Window Length**: 60 frames (2.5 seconds at 24 FPS)
* **Stride**: 12 frames (0.5 seconds)

---

## 2. Coalesced Shape Ratio & Fallback Logic
To simplify the feature space and avoid collinearity while preserving detection safety, **Bounding Box Aspect Ratio is merged into Skeleton Spread Ratio**. 

For any given frame/step, the shape ratio is computed as:
$$\text{Coalesced Shape Ratio} = \begin{cases} \text{Skeleton Spread Ratio} = \frac{X_{\text{max}} - X_{\text{min}}}{Y_{\text{max}} - Y_{\text{min}}} & \text{if skeleton keypoints are visible/valid} \\ \text{BBox Aspect Ratio} = \frac{\text{BBox Width}}{\text{BBox Height}} & \text{if skeleton is not visible/invalid} \end{cases}$$

---

## 3. Engineered Feature Directory

### Group A: Posture Geometry (2D Image Space)
These features characterise body posture using YOLO-Pose keypoints. To generalise across varying camera distances, all spatial distances are normalised by body scale ($BodySize = BBoxDiagonal$).

| Feature Name | Description | Purpose |
| :--- | :--- | :--- |
| `torso_angle_mean` | Average angle of the torso vector (hip center to shoulder center) relative to horizontal. | Standing ($>70^\circ$) vs. Lying ($<25^\circ$). |
| `torso_angle_std` | Standard deviation of torso angle. | Captures sudden torso rotation during a fall. |
| `head_hip_compression_mean` | Average ratio of vertical nose-to-hip Y-distance to bounding box height. | Bending and crouching ($<0.45$) vs. standing ($>0.75$). |
| `hip_ankle_vertical_diff_mean` | Average vertical image distance between hip center and ankle midpoint, normalised. | Standing/running (high vertical split) vs. lying flat. |
| `skeleton_spread_ratio_mean` | Average **Coalesced Shape Ratio** across the window. Falls back to BBox Aspect Ratio if the skeleton is not visible. | Standing (narrow, $<0.6$) vs. lying (wide, $>1.2$). |
| `skeleton_spread_ratio_max` | Maximum **Coalesced Shape Ratio** observed in the window. Falls back to maximum BBox Aspect Ratio if the skeleton is not visible. | Captures brief horizontal layout expansions. |

---

### Group B: Locomotion & Speed Dynamics
These features evaluate movement speeds from both floor contact points and body size changes.

| Feature Name | Description | Purpose |
| :--- | :--- | :--- |
| `ground_speed_mean` | Average frame-over-frame displacement of the ground point (ankle midpoint or box bottom-center), normalised by body height. | Distinguishes walking ($0.2–0.8$) vs. running ($>1.10$). |
| `ground_speed_max` | Maximum ground speed recorded in the window. | Identifies peak velocity during a sprint or fall transition. |
| `scale_speed_mean` | Average normalised change in bounding box height: $\frac{\|H_t - H_{t-1}\|}{H_t \cdot \Delta t}$. | Captures speed toward/away from camera (perspective correction). |
| `combined_speed_mean` | Average of $GroundSpeed + 0.45 \cdot ScaleSpeed$. | Primary metric for identifying overall locomotion velocity. |
| `combined_speed_std` | Standard deviation of combined speed. | Running exhibits high stable speed; falls exhibit a sudden spike. |
| `body_speed_max` | Maximum speed of body center (average of shoulders & hips). | Detects rapid downward acceleration during a collapse. |
| `body_acceleration_max` | Maximum change in body center speed over consecutive frames. | Distinguishes sudden fall drop from constant speed running. |

---

### Group C: 15-Point Periodic Time-Series Features (Decimated Temporal Resolution)
Rather than manually calculating difference deltas over arbitrary segments, we sample the 60-frame window at a regular stride of **4 frames**. This yields exactly **15 discrete sample steps** (frames 0, 4, 8, 12, 16, 20, 24, 28, 32, 36, 40, 44, 48, 52, 56). 

At each sample step $i \in \{0, 1, ..., 14\}$, we extract the local normalised posture and motion metrics. This flattens into $15 \times 8 = 120$ columns, letting the tree classifier learn complex non-linear temporal relationships.

| Column Name Format | Feature Type | Normalisation / Range |
| :--- | :--- | :--- |
| `step_torso_angle_t{i}` | Torso vector angle relative to horizontal at step $i$. | Range: $0^\circ$ to $90^\circ$. |
| `step_compression_t{i}` | Vertical head-hip distance divided by box height at step $i$. | Normalised ratio. |
| `step_spread_ratio_t{i}` | **Coalesced Shape Ratio** at step $i$. Falls back to BBox Aspect Ratio if the skeleton is not visible. | Normalised ratio. |
| `step_combined_speed_t{i}` | Normalized combined ground + scale speed at step $i$. | Speed normalized by body height. |
| `step_hip_ankle_t{i}` | Relative vertical distance between hip center and ankle midpoint at step $i$. | Normalised ratio. |
| `step_ground_speed_t{i}` | Normalized ground displacement speed at step $i$. | Speed normalized by body height. |
| `step_scale_speed_t{i}` | Normalized change in bounding box height at step $i$. | Speed normalized by body height. |
| `step_body_speed_t{i}` | Normalized speed of the body center at step $i$. | Speed normalized by body height. |

#### Why this Decimation works:
1. **lowers dimensionality**: Keeps temporal features to exactly 120 inputs, reducing model overfitting.
2. **Filters Noise**: Downsampling from 24 FPS to 6 FPS acts as a natural smoothing filter, removing camera jitter.
3. **Learns Time Transitions**: Allows tree splits like: `if step_torso_angle_t10 < 30 and step_torso_angle_t2 > 70` $\rightarrow$ `fall_transition`.

---

### Group D: Final Window Posture & Stillness
Evaluates the final 1.0 second (last 24 frames) of the window.

| Feature Name | Description | Purpose |
| :--- | :--- | :--- |
| `final_lying_score` | A combined metric aggregating low torso angle, wide coalesced shape ratio, and low speed in the final second. | Specifically flags the "lying still on floor" state. |
| `final_1s_body_speed_mean` | Average body center speed in the last second. | Distinguishes running (active movement) from fall (stillness). |
| `final_1s_joint_motion_mean` | Average (mean) of joint displacements in the last second. | Distinguishes constant-speed walking (high mean displacement, low std) from a fallen worker lying still (near-zero mean, low std). |
| `final_1s_joint_motion_std` | Standard deviation of joint positions in the last second. | Crouching/kneeling workers still show hand/head movements; fallen workers are typically motionless. |

---

### Group E: Quality Control & Missing Values
Safeguards the sequence against noisy or missing coordinate frames.

| Feature Name | Description | Purpose |
| :--- | :--- | :--- |
| `avg_keypoint_confidence` | Mean confidence score across all 17 skeleton keypoints in the window. | Tells the model to ignore noisy/occluded skeletons. |
| `missing_ankle_ratio` | Percentage of frames in the window where ankle keypoints fall below confidence $0.1$. | Adjusts weight of ground-speed measurements if ankles are occluded. |

#### Missing Value Strategy (For Group C Time-series):
If keypoints are lost/occluded on a specific sample step (e.g. frame 24), apply **linear interpolation** from the nearest valid steps in the window before flattening, preventing `NaN` inputs.

---

## 4. How the Classifier Learns the Boundaries

```mermaid
decision_matrix
  Class[falling]  --> Posture[Torso Angle t0: Vertical -> Torso Angle t14: Horizontal] & Motion[Speed t6: Spike -> Speed t14: Near-Zero]
  Class[running]  --> Posture[Torso Angle: Consistently Upright] & Motion[Speed: Consistently High]
  Class[others]   --> Posture[Torso Angle: Upright/Stable Crouch] & Motion[Speed: Low/Moderate t0-t14]
```
