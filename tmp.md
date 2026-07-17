# Comprehensive Comparison: Running Behavior Detection Strategies

This document presents a detailed comparison between the running detection prototype described in **RUNNING_DETECTION_APPROACH.md** (located in the `fall-detection-app` repository) and the production-level window-based running detection logic implemented in the **AutoLabeling** repository.

---

## 1. Algorithmic Overview

### Approach A: Streaming EMA-Based Heuristic (`RUNNING_DETECTION_APPROACH.md`)
* **Core Mechanism**: Processes video frames sequentially in a streaming fashion.
* **Instant Speed Calculation**: Evaluates the displacement of ankles (ground point) normalized by body height, plus the normalized change in bounding box height (scale speed) to handle perspective:
  $$\text{instant\_speed} = \text{ground\_speed} + 0.45 \times \text{scale\_speed}$$
* **Temporal Smoothing**: Uses a simple frame-by-frame Exponential Moving Average (EMA) to smooth speed coordinates:
  $$\text{speed\_ema} = 0.65 \times \text{speed\_ema\_prev} + 0.35 \times \text{instant\_speed}$$
* **Hysteresis State Machine**:
  * **Enter RUNNING**: Stays in `RUNNING` state if `speed_ema >= 1.10` for $\ge 0.5\text{ seconds}$ consecutively.
  * **Exit RUNNING**: Returns to `WALKING` if `speed_ema < 0.70` for $\ge 1.0\text{ seconds}$ consecutively.

---

### Approach B: Windowed Multiclass Integration (`AutoLabeling` Repository)
* **Core Mechanism**: Analyzes a sliding window of **60 frames** (2.5 seconds at 24 FPS) with a stride of **12 frames** (0.5 seconds).
* **Calibrated Feature Ramping**: Maps raw velocities into a normalized score range $[0.0, 1.0]$ using a linear ramp function (e.g. combined speed mapping from $0.8$ to $1.5$).
* **Unified Locomotion Equation**: Combines multiple speeds and adds a posture-based penalty to prevent speed misclassifications during falls:
  $$\text{running\_score} = w_{\text{combined}} \cdot \text{combined} + w_{\text{ground}} \cdot \text{ground} + w_{\text{body}} \cdot \text{body} + w_{\text{sustained}} \cdot \text{sustained} - w_{\text{fall}} \cdot \text{fall\_inhibition\_score}$$
  *(Defaults: combined=0.35, ground=0.20, body=0.20, sustained=0.25, fall=0.40)*
  
  * `sustained`: Percentage of the 15 downsampled step windows where combined speed score is $\ge 0.5$.
  * `fall_inhibition_score`: The maximum score of lying posture metrics (flat torso, lying score, skeleton spread).
* **Multi-Window Transitions**:
  * **Enter RUNNING**: Triggers `RUNNING` if `running_score` $\ge 0.60$ **AND** `fall_inhibition_score` $< 0.45$ for 2 consecutive windows.
  * **Exit RUNNING**: Exits `RUNNING` if `running_score` $< 0.40$ for 3 consecutive windows.

---

## 2. Key Differences

| Dimension | Streaming EMA Heuristic (Approach A) | Windowed Multiclass Integration (Approach B) |
| :--- | :--- | :--- |
| **Temporal Context** | **Frame-by-frame**: Uses a rolling average of past frames. Immediate response but susceptible to high-frequency noise. | **Sliding Window**: Extracts features across a fixed 60-frame chunk. High robustness, acts as a natural low-pass filter. |
| **Feature Scaling** | **Raw metrics**: Thresholds are applied directly to raw pixel-displacement velocities. Sensitive to varying camera resolutions. | **Normalized ramping**: Speeds are scaled to $[0, 1]$ based on camera calibrations before scoring. |
| **Sustained Verification** | **Timer accumulator**: Counts elapsed seconds above threshold. | **Sub-step decimation**: Calculates speed across 15 downsampled intervals to ensure the motion is active throughout the window. |
| **Fall Inhibition** | **None**: A rapid fall transition can momentarily trigger a false `RUNNING` alert due to the high speed spike. | **Postural Penalty**: Subtracts the fall probability score from the running score, preventing fast collapses from triggering running labels. |
| **Execution Mode** | Online, streaming (low memory footprint, low latency). | Offline or batch-oriented (higher memory footprint, 2.5s buffer latency). |

---

## 3. Which Approach is Better?

### **Approach B (Windowed Multiclass Integration) is superior for safety dataset labeling and auditing.**
* **Postural Safety Integration**: Subtracting the `fall_inhibition_score` from the running score prevents the critical failure mode where a rapid, high-acceleration fall transition is mislabeled as "running".
* **Calibrated Generalization**: Ramping raw velocities into standardized $[0, 1]$ bounds prevents camera height or lens resolution from throwing off thresholds.
* **Segmentation Quality**: State transitions based on consecutive multi-window lookbacks result in cohesive, flicker-free activity intervals.

### **Approach A (Streaming EMA) is better strictly for low-latency Edge/CCTV processing.**
* If real-time, zero-buffer alerts are required on edge hardware (e.g., immediate sirens when a worker sprints), the frame-by-frame EMA is useful due to its low processing overhead and instant output.

---

## 4. Conclusion & Verdict
For the **Auto-Labeling Tool**, **Approach B (Window-Based Integration)** is the ideal solution. It aligns with the multi-class taxonomy, leverages postural indicators to suppress false locomotion triggers during collapses, and produces clean, reproducible segments.
