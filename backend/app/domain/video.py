"""Framework-independent constants and helpers for pose-video labeling."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from backend.app.domain.errors import VideoValidationError


HUMAN_LABELS = ("others", "running", "falling")
SUGGESTION_LABELS = ("running", "falling")
CANONICAL_FPS = 24
WINDOW_LENGTH_FRAMES = 60
FEATURE_SCHEMA_VERSION = "v1"
WINDOW_CONFIG_VERSION = "60-12-24-v1"
TRACKING_CACHE_VERSION = "botsort-dedicated-reid-v3"

DEFAULT_PROJECT_CONFIG: dict[str, Any] = {
    "class_map": {"others": 0, "running": 1, "falling": 2},
    "video": {"canonical_fps": CANONICAL_FPS, "resample_to_canonical_fps": True},
    "pose": {
        "model_name": "yolo26m-pose",
        "model_version": "unresolved",
        "detection_confidence": 0.25,
        "keypoint_confidence": 0.10,
    },
    "tracking": {
        "tracker": "botsort",
        "tracker_config_version": TRACKING_CACHE_VERSION,
    },
    "window": {
        "length_frames": WINDOW_LENGTH_FRAMES,
        "stride_frames": 12,
        "final_period_frames": 24,
    },
    "window_labeling": {
        "falling_min_overlap_frames": 8,
        "falling_final_period_ratio": 0.50,
        "running_min_ratio": 0.50,
        "others_min_ratio": 0.70,
        "priority": ["falling", "running", "others"],
    },
    "quality": {
        "min_average_keypoint_confidence": 0.35,
        "max_missing_ankle_ratio": 0.40,
        "min_valid_frame_ratio": 0.70,
        "max_interpolation_gap_frames": 6,
    },
    "features": {"feature_schema_version": FEATURE_SCHEMA_VERSION},
    "suggestions": {
        "default_source": "Threshold",
        "threshold_profile_version": "v1",
        "minimum_segment_frames": 6,
        "merge_gap_frames": 6,
    },
    "annotation": {"annotation_schema_version": "v1"},
    "export": {"schema_version": "v1"},
}

DEFAULT_THRESHOLD_PROFILE: dict[str, Any] = {
    "transforms": {
        "torso_angle": [25.0, 75.0],
        "compression": [0.32, 0.85],
        "hip_ankle": [0.28, 0.90],
        "spread": [0.80, 1.60],
        "fall_acceleration": [1.5, 6.0],
        "stillness_motion": [0.01, 0.20],
        "running_combined_speed": [0.8, 1.5],
        "running_ground_speed": [0.7, 1.3],
        "running_body_speed": [0.6, 1.2],
    },
    "fall": {
        "transition_weights": {"accel": 0.35, "rotation": 0.25, "spread": 0.20, "flatten": 0.20},
        "state_weights": {"torso": 0.30, "spread": 0.20, "lying": 0.30, "stillness": 0.20},
        "transition_entry": 0.65,
        "state_entry": 0.55,
        "lying_entry": 0.75,
        "exit_threshold": 0.35,
        "entry_consecutive": 2,
        "exit_consecutive": 3,
    },
    "running": {
        "weights": {"combined": 0.35, "ground": 0.20, "body": 0.20, "sustained": 0.25, "fall": 0.40},
        "entry_threshold": 0.60,
        "exit_threshold": 0.40,
        "entry_consecutive": 2,
        "exit_consecutive": 3,
        "max_fall_inhibition": 0.45,
    },
    "quality": {"min_average_keypoint_confidence": 0.35, "min_valid_frame_ratio": 0.70},
    "merge_gap_frames": 6,
}


def project_config() -> dict[str, Any]:
    """Return an isolated default project configuration."""

    return deepcopy(DEFAULT_PROJECT_CONFIG)


def threshold_profile_config() -> dict[str, Any]:
    """Return an isolated default threshold profile."""

    return deepcopy(DEFAULT_THRESHOLD_PROFILE)


def validate_project_config(config: dict[str, Any]) -> None:
    """Protect fixed class/timeline contracts while allowing threshold tuning."""

    if config.get("class_map") != DEFAULT_PROJECT_CONFIG["class_map"]:
        raise VideoValidationError("Video projects must use exactly others=0, running=1, falling=2")
    window = config.get("window", {})
    expected = DEFAULT_PROJECT_CONFIG["window"]
    if any(int(window.get(key, -1)) != value for key, value in expected.items()):
        raise VideoValidationError("Window configuration must remain length=60, stride=12, final_period=24")
    if float(config.get("video", {}).get("canonical_fps", 0)) != CANONICAL_FPS:
        raise VideoValidationError("Canonical FPS must be 24")


def canonical_frame_mapping(
    original_fps: float, original_frames: int, canonical_fps: int = CANONICAL_FPS
) -> list[tuple[int, int, float]]:
    """Create deterministic canonical-frame to source-frame/timestamp rows."""

    if original_fps <= 0 or original_frames <= 0:
        raise VideoValidationError("Video FPS and frame count must be positive")
    canonical_count = max(1, round(original_frames * canonical_fps / original_fps))
    result: list[tuple[int, int, float]] = []
    for frame in range(canonical_count):
        timestamp = frame / canonical_fps
        original = min(original_frames - 1, int(round(timestamp * original_fps)))
        result.append((frame, original, timestamp))
    return result
