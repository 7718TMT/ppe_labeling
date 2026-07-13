"""Deterministic Group A-E pose feature extraction and score transforms."""

from __future__ import annotations

import math
from statistics import fmean, pstdev
from typing import Any, Iterable

from backend.app.domain.video import CANONICAL_FPS, FEATURE_SCHEMA_VERSION


COCO = {"nose": 0, "left_shoulder": 5, "right_shoulder": 6, "left_hip": 11, "right_hip": 12, "left_ankle": 15, "right_ankle": 16}
STEP_METRICS = (
    "torso_angle",
    "compression",
    "spread_ratio",
    "combined_speed",
    "hip_ankle",
    "ground_speed",
    "scale_speed",
    "body_speed",
)


def ramp(value: float, low: float, high: float) -> float:
    """Linearly map a raw value into the closed interval zero to one."""

    if high <= low:
        raise ValueError("Transform high bound must be greater than low bound")
    return min(1.0, max(0.0, (value - low) / (high - low)))


def _mean(values: Iterable[float | None], default: float = 0.0) -> float:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return fmean(clean) if clean else default


def _std(values: Iterable[float | None]) -> float:
    clean = [float(value) for value in values if value is not None and math.isfinite(float(value))]
    return pstdev(clean) if len(clean) > 1 else 0.0


def _distance(first: tuple[float, float], second: tuple[float, float]) -> float:
    return math.hypot(first[0] - second[0], first[1] - second[1])


def _point(frame: dict[str, Any], names: tuple[str, ...], threshold: float) -> tuple[float, float] | None:
    points: list[tuple[float, float]] = []
    for name in names:
        index = COCO[name]
        scores = frame.get("keypoint_scores", [])
        keypoints = frame.get("keypoints", [])
        if index >= len(scores) or index >= len(keypoints) or float(scores[index]) < threshold:
            continue
        point = keypoints[index]
        points.append((float(point[0]), float(point[1])))
    if len(points) != len(names):
        return None
    return (_mean(point[0] for point in points), _mean(point[1] for point in points))


def _frame_geometry(frame: dict[str, Any] | None, keypoint_threshold: float) -> dict[str, Any]:
    if frame is None:
        return {name: None for name in (*STEP_METRICS, "body_center", "ground_point", "bbox_height", "body_size", "joint_positions")}
    bbox = [float(value) for value in frame["bbox"]]
    width = max(0.0, bbox[2] - bbox[0])
    height = max(0.0, bbox[3] - bbox[1])
    diagonal = math.hypot(width, height)
    shoulder = _point(frame, ("left_shoulder", "right_shoulder"), keypoint_threshold)
    hip = _point(frame, ("left_hip", "right_hip"), keypoint_threshold)
    ankles = _point(frame, ("left_ankle", "right_ankle"), keypoint_threshold)
    nose = _point(frame, ("nose",), keypoint_threshold)
    torso_length = _distance(shoulder, hip) if shoulder and hip else 0.0
    body_size = diagonal or height or torso_length or 1.0
    torso = None
    if shoulder and hip:
        torso = math.degrees(math.atan2(abs(shoulder[1] - hip[1]), abs(shoulder[0] - hip[0])))
    compression = abs(nose[1] - hip[1]) / height if nose and hip and height else None
    hip_ankle = abs(hip[1] - ankles[1]) / body_size if hip and ankles else None
    valid_points = [
        (float(point[0]), float(point[1]))
        for point, score in zip(frame.get("keypoints", []), frame.get("keypoint_scores", []), strict=False)
        if float(score) >= keypoint_threshold
    ]
    if len(valid_points) >= 2:
        spread_height = max(point[1] for point in valid_points) - min(point[1] for point in valid_points)
        spread = (max(point[0] for point in valid_points) - min(point[0] for point in valid_points)) / spread_height if spread_height else width / height if height else 0.0
    else:
        spread = width / height if height else 0.0
    body_center = ((_mean((shoulder[0], hip[0])), _mean((shoulder[1], hip[1])))) if shoulder and hip else None
    ground = ankles or ((bbox[0] + bbox[2]) / 2.0, bbox[3])
    return {
        "torso_angle": torso,
        "compression": compression,
        "spread_ratio": spread,
        "hip_ankle": hip_ankle,
        "body_center": body_center,
        "ground_point": ground,
        "bbox_height": height,
        "body_size": body_size,
        "joint_positions": valid_points,
        "ground_speed": None,
        "scale_speed": None,
        "combined_speed": None,
        "body_speed": None,
    }


def _add_motion(metrics: list[dict[str, Any]], fps: int) -> None:
    delta_time = 1.0 / fps
    for index in range(1, len(metrics)):
        current = metrics[index]
        previous = metrics[index - 1]
        if current["ground_point"] and previous["ground_point"] and current["bbox_height"]:
            current["ground_speed"] = _distance(current["ground_point"], previous["ground_point"]) / (current["bbox_height"] * delta_time)
        if current["bbox_height"] and previous["bbox_height"]:
            current["scale_speed"] = abs(current["bbox_height"] - previous["bbox_height"]) / (current["bbox_height"] * delta_time)
        if current["ground_speed"] is not None or current["scale_speed"] is not None:
            current["combined_speed"] = (current["ground_speed"] or 0.0) + 0.45 * (current["scale_speed"] or 0.0)
        if current["body_center"] and previous["body_center"] and current["body_size"]:
            current["body_speed"] = _distance(current["body_center"], previous["body_center"]) / (current["body_size"] * delta_time)


def _interpolate(values: list[float | None], max_gap: int) -> tuple[list[float | None], list[str]]:
    result = list(values)
    provenance = ["observed" if value is not None else "missing" for value in values]
    index = 0
    while index < len(result):
        if result[index] is not None:
            index += 1
            continue
        start = index
        while index < len(result) and result[index] is None:
            index += 1
        end = index - 1
        gap = end - start + 1
        left = start - 1
        right = index
        if gap <= max_gap and left >= 0 and right < len(result) and result[left] is not None and result[right] is not None:
            for offset, target in enumerate(range(start, right), start=1):
                fraction = offset / (gap + 1)
                result[target] = float(result[left]) + (float(result[right]) - float(result[left])) * fraction
                provenance[target] = "interpolated"
    return result, provenance


def feature_columns() -> list[str]:
    """Return the exact stable external-model feature order for schema v1."""

    summary = [
        "torso_angle_mean", "torso_angle_std", "head_hip_compression_mean",
        "hip_ankle_vertical_diff_mean", "skeleton_spread_ratio_mean", "skeleton_spread_ratio_max",
        "ground_speed_mean", "ground_speed_max", "scale_speed_mean", "combined_speed_mean",
        "combined_speed_std", "body_speed_max", "body_acceleration_max",
    ]
    steps = [f"step_{name}_t{index}" for index in range(15) for name in STEP_METRICS]
    final = ["final_lying_score", "final_1s_body_speed_mean", "final_1s_joint_motion_mean", "final_1s_joint_motion_std"]
    quality = ["avg_keypoint_confidence", "missing_ankle_ratio", "valid_frame_ratio", "missing_hip_ratio", "track_gap_count", "skeleton_jump_score"]
    return [*summary, *steps, *final, *quality]


def extract_window_features(
    frames: list[dict[str, Any] | None],
    *,
    keypoint_threshold: float = 0.10,
    max_interpolation_gap: int = 6,
    min_valid_frame_ratio: float = 0.70,
) -> dict[str, Any]:
    """Extract all Group A-E features from one 60-frame track window."""

    if len(frames) != 60:
        raise ValueError("Feature windows must contain exactly 60 canonical frames")
    metrics = [_frame_geometry(frame, keypoint_threshold) for frame in frames]
    _add_motion(metrics, CANONICAL_FPS)
    valid_frame_ratio = sum(frame is not None for frame in frames) / len(frames)
    arrays: dict[str, list[float | None]] = {}
    provenance: dict[str, list[str]] = {}
    for name in STEP_METRICS:
        arrays[name], provenance[name] = _interpolate([item[name] for item in metrics], max_interpolation_gap)
    body_speeds = arrays["body_speed"]
    accelerations = [
        abs(float(current) - float(previous)) * CANONICAL_FPS
        if current is not None and previous is not None else None
        for previous, current in zip(body_speeds, body_speeds[1:], strict=False)
    ]
    raw: dict[str, float] = {
        "torso_angle_mean": _mean(arrays["torso_angle"]),
        "torso_angle_std": _std(arrays["torso_angle"]),
        "head_hip_compression_mean": _mean(arrays["compression"]),
        "hip_ankle_vertical_diff_mean": _mean(arrays["hip_ankle"]),
        "skeleton_spread_ratio_mean": _mean(arrays["spread_ratio"]),
        "skeleton_spread_ratio_max": max((value for value in arrays["spread_ratio"] if value is not None), default=0.0),
        "ground_speed_mean": _mean(arrays["ground_speed"]),
        "ground_speed_max": max((value for value in arrays["ground_speed"] if value is not None), default=0.0),
        "scale_speed_mean": _mean(arrays["scale_speed"]),
        "combined_speed_mean": _mean(arrays["combined_speed"]),
        "combined_speed_std": _std(arrays["combined_speed"]),
        "body_speed_max": max((value for value in body_speeds if value is not None), default=0.0),
        "body_acceleration_max": max((value for value in accelerations if value is not None), default=0.0),
    }
    for step, frame_index in enumerate(range(0, 60, 4)):
        for name in STEP_METRICS:
            raw[f"step_{name}_t{step}"] = float(arrays[name][frame_index] or 0.0)
    final_metrics = metrics[-24:]
    final_body = arrays["body_speed"][-24:]
    joint_motion: list[float] = []
    for previous, current in zip(final_metrics, final_metrics[1:], strict=False):
        previous_points = previous["joint_positions"]
        current_points = current["joint_positions"]
        if previous_points and current_points and len(previous_points) == len(current_points):
            joint_motion.append(_mean(_distance(first, second) for first, second in zip(previous_points, current_points, strict=True)) / max(current["body_size"], 1.0))
    final_torso = _mean(arrays["torso_angle"][-24:])
    final_spread = _mean(arrays["spread_ratio"][-24:])
    final_still = _mean(joint_motion)
    raw.update({
        "final_lying_score": _mean((1.0 - ramp(final_torso, 25.0, 75.0), ramp(final_spread, 0.8, 1.6), 1.0 - ramp(final_still, 0.01, 0.20))),
        "final_1s_body_speed_mean": _mean(final_body),
        "final_1s_joint_motion_mean": final_still,
        "final_1s_joint_motion_std": _std(joint_motion),
    })
    confidences = [float(score) for frame in frames if frame for score in frame.get("keypoint_scores", [])]
    missing_ankles = sum(
        frame is None or any(float(frame.get("keypoint_scores", [0.0] * 17)[index]) < keypoint_threshold for index in (15, 16))
        for frame in frames
    ) / len(frames)
    missing_hips = sum(
        frame is None or any(float(frame.get("keypoint_scores", [0.0] * 17)[index]) < keypoint_threshold for index in (11, 12))
        for frame in frames
    ) / len(frames)
    observed_indexes = [index for index, frame in enumerate(frames) if frame]
    gaps = sum((right - left) > 1 for left, right in zip(observed_indexes, observed_indexes[1:], strict=False))
    centers = [metric["body_center"] for metric in metrics]
    jumps = [
        _distance(current, previous) / max(metrics[index]["body_size"], 1.0)
        for index, (previous, current) in enumerate(zip(centers, centers[1:], strict=False), start=1)
        if previous and current
    ]
    raw.update({
        "avg_keypoint_confidence": _mean(confidences),
        "missing_ankle_ratio": missing_ankles,
        "valid_frame_ratio": valid_frame_ratio,
        "missing_hip_ratio": missing_hips,
        "track_gap_count": float(gaps),
        "skeleton_jump_score": max(jumps, default=0.0),
    })
    step_provenance = {
        f"step_{name}_t{step}": provenance[name][frame_index]
        for step, frame_index in enumerate(range(0, 60, 4))
        for name in STEP_METRICS
    }
    quality_status = "good" if valid_frame_ratio >= min_valid_frame_ratio else "low_quality"
    return {
        "feature_schema_version": FEATURE_SCHEMA_VERSION,
        "raw": raw,
        "provenance": step_provenance,
        "quality": {
            "status": quality_status,
            "valid_frame_ratio": valid_frame_ratio,
            "observed_steps": sum(value == "observed" for value in step_provenance.values()),
            "interpolated_steps": sum(value == "interpolated" for value in step_provenance.values()),
            "missing_steps": sum(value == "missing" for value in step_provenance.values()),
        },
    }


def transform_features(raw: dict[str, float], profile: dict[str, Any]) -> dict[str, float]:
    """Transform raw window features into inspectable normalized scores."""

    transforms = profile["transforms"]
    score = {
        "torso_horizontal_score": 1.0 - ramp(raw["torso_angle_mean"], *transforms["torso_angle"]),
        "compression_score": 1.0 - ramp(raw["head_hip_compression_mean"], *transforms["compression"]),
        "hip_ankle_flat_score": 1.0 - ramp(raw["hip_ankle_vertical_diff_mean"], *transforms["hip_ankle"]),
        "spread_score": ramp(raw["skeleton_spread_ratio_mean"], *transforms["spread"]),
        "fall_acceleration_score": ramp(raw["body_acceleration_max"], *transforms["fall_acceleration"]),
        "final_stillness_score": 1.0 - ramp(raw["final_1s_joint_motion_mean"], *transforms["stillness_motion"]),
        "final_lying_score_norm": min(1.0, max(0.0, raw["final_lying_score"])),
        "combined_locomotion_score": ramp(raw["combined_speed_mean"], *transforms["running_combined_speed"]),
        "ground_locomotion_score": ramp(raw["ground_speed_mean"], *transforms["running_ground_speed"]),
        "body_locomotion_score": ramp(raw["body_speed_max"], *transforms["running_body_speed"]),
    }
    step_scores = [
        ramp(raw[f"step_combined_speed_t{index}"], *transforms["running_combined_speed"])
        for index in range(15)
    ]
    score["sustained_locomotion_score"] = sum(value >= 0.5 for value in step_scores) / len(step_scores)
    score["fall_inhibition_score"] = max(score["torso_horizontal_score"], score["final_lying_score_norm"], score["spread_score"])
    torso_change = ramp(max(0.0, raw["step_torso_angle_t0"] - raw["step_torso_angle_t14"]), 15.0, 55.0)
    spread_change = ramp(max(0.0, raw["step_spread_ratio_t14"] - raw["step_spread_ratio_t0"]), 0.2, 0.9)
    flat_change = ramp(max(0.0, raw["step_hip_ankle_t0"] - raw["step_hip_ankle_t14"]), 0.15, 0.65)
    fall = profile["fall"]
    transition = fall["transition_weights"]
    state = fall["state_weights"]
    score["torso_rotation_change_score"] = torso_change
    score["spread_change_score"] = spread_change
    score["hip_ankle_flat_change_score"] = flat_change
    score["fall_transition_score"] = min(1.0, transition["accel"] * score["fall_acceleration_score"] + transition["rotation"] * torso_change + transition["spread"] * spread_change + transition["flatten"] * flat_change)
    score["fall_state_score"] = min(1.0, state["torso"] * score["torso_horizontal_score"] + state["spread"] * score["spread_score"] + state["lying"] * score["final_lying_score_norm"] + state["stillness"] * score["final_stillness_score"])
    weights = profile["running"]["weights"]
    score["running_score"] = min(1.0, max(0.0, weights["combined"] * score["combined_locomotion_score"] + weights["ground"] * score["ground_locomotion_score"] + weights["body"] * score["body_locomotion_score"] + weights["sustained"] * score["sustained_locomotion_score"] - weights["fall"] * score["fall_inhibition_score"]))
    return score
