"""Window generation, feature caches, and threshold suggestion workflows."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from backend.app.domain.errors import VideoValidationError
from backend.app.domain.video import FEATURE_SCHEMA_VERSION, WINDOW_CONFIG_VERSION, threshold_profile_config
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_features import extract_window_features, transform_features


class VideoFeatureService:
    """Generate deterministic windows and auditable feature-based suggestions."""

    def __init__(self, repository: VideoRepository, storage: VideoStorageRepository) -> None:
        self.repository = repository
        self.storage = storage

    def generate_windows(self, video_id: str) -> list[dict[str, Any]]:
        video = self.repository.get_video(video_id)
        config = self.repository.get_project(video["project_id"])["config"]
        length = int(config["window"]["length_frames"])
        stride = int(config["window"]["stride_frames"])
        final_period = int(config["window"]["final_period_frames"])
        rules = config["window_labeling"]
        segments = self.repository.list_segments(video_id)
        generated: list[dict[str, Any]] = []
        for track in self.repository.list_tracks(video_id, include_excluded=False):
            track_id = int(track["track_id"])
            for start in range(int(track["start_frame"]), int(track["end_frame"]) - length + 2, stride):
                end = start + length - 1
                label, reason = self._window_label(start, end, final_period, segments, track_id, rules)
                quality_score = min(float(track["avg_keypoint_confidence"]), float(track["valid_frame_ratio"]))
                low_quality = (
                    float(track["valid_frame_ratio"]) < float(config["quality"]["min_valid_frame_ratio"])
                    or float(track["avg_keypoint_confidence"]) < float(config["quality"]["min_average_keypoint_confidence"])
                )
                status = "low_quality" if low_quality else "good" if label else "unlabeled"
                include = bool(label) and not low_quality and bool(track["include_in_export"])
                generated.append({
                    "track_id": track_id, "start_frame": start, "end_frame": end,
                    "label": label, "label_reason": reason, "quality_score": quality_score,
                    "quality_status": status, "include_in_export": int(include),
                    "exclude_reason": "low_pose_quality" if low_quality else None if label else "unresolved_label",
                    "window_config_version": WINDOW_CONFIG_VERSION, "feature_status": "pending", "stale": 0,
                })
        self.repository.replace_windows(video_id, generated)
        self.repository.update_video(video_id, window_cache_version=WINDOW_CONFIG_VERSION)
        return self.repository.list_windows(video_id)

    def list_windows(self, video_id: str, track_id: int | None = None) -> list[dict[str, Any]]:
        return self.repository.list_windows(video_id, track_id)

    def review_window(self, video_id: str, window_id: str, include: bool, reason: str | None) -> dict[str, Any]:
        if not include and not reason:
            raise VideoValidationError("An exclusion reason is required")
        self.repository.execute(
            "UPDATE generated_windows SET include_in_export=?,exclude_reason=?,updated_at=CURRENT_TIMESTAMP WHERE window_id=? AND video_id=?",
            (int(include), None if include else reason, window_id, video_id),
        )
        return self.repository.one("SELECT * FROM generated_windows WHERE window_id=?", (window_id,)) or {}

    def list_profiles(self, project_id: str) -> list[dict[str, Any]]:
        return self.repository.list_threshold_profiles(project_id)

    @staticmethod
    def _window_label(
        start: int, end: int, final_period: int, segments: list[dict[str, Any]],
        track_id: int, rules: dict[str, Any],
    ) -> tuple[str | None, str]:
        counts = {"others": 0, "running": 0, "falling": 0}
        final_falling = 0
        final_start = end - final_period + 1
        for segment in segments:
            if int(segment["track_id"]) != track_id or not segment["include_in_export"]:
                continue
            overlap = max(0, min(end, int(segment["end_frame"])) - max(start, int(segment["start_frame"])) + 1)
            counts[segment["label"]] += overlap
            if segment["label"] == "falling":
                final_falling += max(0, min(end, int(segment["end_frame"])) - max(final_start, int(segment["start_frame"])) + 1)
        valid = sum(counts.values())
        if counts["falling"] >= int(rules["falling_min_overlap_frames"]):
            return "falling", "falling_min_overlap"
        if final_falling / final_period >= float(rules["falling_final_period_ratio"]):
            return "falling", "falling_final_period"
        if valid and counts["running"] / valid >= float(rules["running_min_ratio"]):
            return "running", "running_ratio"
        if valid and counts["others"] / valid >= float(rules["others_min_ratio"]):
            return "others", "others_ratio"
        return None, "unresolved"

    def extract_features(self, video_id: str) -> dict[str, Any]:
        video = self.repository.get_video(video_id)
        if not video.get("pose_cache_version"):
            raise VideoValidationError("Pose/tracking cache is not ready")
        project = self.repository.get_project(video["project_id"])
        config = project["config"]
        windows = self.repository.list_windows(video_id) or self.generate_windows(video_id)
        pose_path = self.storage.artifact_path(
            video["project_id"], "pose", video_id, video["pose_cache_version"]
        )
        pose = self.storage.read_json(pose_path)
        by_track: dict[int, dict[int, dict[str, Any]]] = {}
        for frame in pose.get("frames", []):
            frame_index = int(frame["frame_index"])
            for detection in frame.get("tracks", []):
                by_track.setdefault(int(detection["track_id"]), {})[frame_index] = detection
        profile_id = project.get("active_threshold_profile_id")
        profile = self.repository.get_threshold_profile(profile_id)["config"] if profile_id else threshold_profile_config()
        records: list[dict[str, Any]] = []
        for window in windows:
            track_frames = by_track.get(int(window["track_id"]), {})
            frames = [track_frames.get(index) for index in range(int(window["start_frame"]), int(window["end_frame"]) + 1)]
            features = extract_window_features(
                frames,
                keypoint_threshold=float(config["pose"]["keypoint_confidence"]),
                max_interpolation_gap=int(config["quality"]["max_interpolation_gap_frames"]),
                min_valid_frame_ratio=float(config["quality"]["min_valid_frame_ratio"]),
            )
            features["transformed"] = transform_features(features["raw"], profile)
            features.update({
                "window_id": window["window_id"], "video_id": video_id,
                "track_id": window["track_id"], "start_frame": window["start_frame"],
                "end_frame": window["end_frame"], "label": window["label"],
            })
            records.append(features)
            self.repository.execute(
                "UPDATE generated_windows SET feature_status='ready',quality_status=?,quality_score=?,include_in_export=CASE WHEN ?='low_quality' THEN 0 ELSE include_in_export END,exclude_reason=CASE WHEN ?='low_quality' THEN 'low_pose_quality' ELSE exclude_reason END WHERE window_id=?",
                (features["quality"]["status"], features["raw"]["avg_keypoint_confidence"], features["quality"]["status"], features["quality"]["status"], window["window_id"]),
            )
        artifact = {
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "threshold_profile_id": profile_id,
            "video_id": video_id,
            "windows": records,
        }
        path = self.storage.artifact_path(video["project_id"], "features", video_id, FEATURE_SCHEMA_VERSION)
        self.storage.write_json(path, artifact)
        self.repository.update_video(video_id, feature_cache_version=FEATURE_SCHEMA_VERSION, processing_status="feature_ready")
        return artifact

    def feature_range(self, video_id: str, track_id: int | None = None, start: int | None = None, end: int | None = None) -> list[dict[str, Any]]:
        video = self.repository.get_video(video_id)
        version = video.get("feature_cache_version")
        if not version:
            return []
        artifact = self.storage.read_json(self.storage.artifact_path(video["project_id"], "features", video_id, version))
        return [
            record for record in artifact["windows"]
            if (track_id is None or int(record["track_id"]) == track_id)
            and (start is None or int(record["end_frame"]) >= start)
            and (end is None or int(record["start_frame"]) <= end)
        ]

    def generate_threshold_suggestions(self, video_id: str, profile_id: str | None = None) -> list[dict[str, Any]]:
        video = self.repository.get_video(video_id)
        project = self.repository.get_project(video["project_id"])
        selected = profile_id or project.get("active_threshold_profile_id")
        if not selected:
            raise VideoValidationError("No threshold profile is selected")
        profile_record = self.repository.get_threshold_profile(selected)
        profile = profile_record["config"]
        features = self.feature_range(video_id)
        if not features:
            self.extract_features(video_id)
            features = self.feature_range(video_id)
        candidates: list[dict[str, Any]] = []
        by_track: dict[int, list[dict[str, Any]]] = {}
        for record in features:
            by_track.setdefault(int(record["track_id"]), []).append(record)
        for track_id, records in by_track.items():
            records.sort(key=lambda item: item["start_frame"])
            current_state = None
            consecutive_exit = 0
            state_config = lambda state: profile["fall" if state == "falling" else state]
            for index, record in enumerate(records):
                raw, score = record["raw"], record["transformed"]
                # Human label ``falling`` maps to the threshold profile's
                # concise ``fall`` section.
                quality_ok = raw["avg_keypoint_confidence"] >= profile["quality"]["min_average_keypoint_confidence"] and raw["valid_frame_ratio"] >= profile["quality"]["min_valid_frame_ratio"]
                if not quality_ok:
                    if current_state:
                        consecutive_exit += 1
                        if consecutive_exit >= state_config(current_state).get("exit_consecutive", 3):
                            current_state = None
                    continue

                fall_lookback = profile["fall"]["entry_consecutive"]
                previous_fall = records[max(0, index - fall_lookback + 1):index + 1]
                fall_condition = len(previous_fall) >= fall_lookback and all(
                    (item["transformed"]["fall_transition_score"] >= profile["fall"]["transition_entry"] or
                     item["transformed"]["fall_state_score"] >= profile["fall"]["state_entry"]) for item in previous_fall
                )
                lying_condition = len(records[max(0, index - 1):index + 1]) >= 2 and all(
                    item["transformed"]["final_lying_score_norm"] >= profile["fall"]["lying_entry"] for item in records[max(0, index - 1):index + 1]
                )
                
                # Temporarily disabled 2 consecutive windows requirement for testing (force run_lookback = 1)
                run_lookback = 1
                previous_run = records[max(0, index - run_lookback + 1):index + 1]
                running_condition = len(previous_run) >= run_lookback and all(
                    item["transformed"]["running_score"] >= profile["running"]["entry_threshold"]
                    and item["transformed"]["fall_inhibition_score"] < profile["running"]["max_fall_inhibition"] for item in previous_run
                )

                if fall_condition or lying_condition:
                    current_state = "falling"
                    consecutive_exit = 0
                elif running_condition:
                    current_state = "running"
                    consecutive_exit = 0
                elif current_state:
                    if current_state == "falling":
                        is_exit = score["fall_state_score"] < profile["fall"]["exit_threshold"] and score["fall_inhibition_score"] < profile["fall"]["exit_threshold"]
                    elif current_state == "running":
                        is_exit = score["running_score"] < profile["running"]["exit_threshold"]
                    else:
                        is_exit = False

                    if is_exit:
                        consecutive_exit += 1
                        if consecutive_exit >= state_config(current_state).get("exit_consecutive", 3):
                            current_state = None
                    else:
                        consecutive_exit = 0

                if current_state == "falling":
                    candidates.append(self._candidate(track_id, record, "falling", max(score["fall_transition_score"], score["fall_state_score"], score["final_lying_score_norm"]), ["fall_state_machine"], score))
                elif current_state == "running":
                    candidates.append(self._candidate(track_id, record, "running", score["running_score"], ["run_state_machine"], score))
        merged = self._merge_candidates(candidates, int(profile["merge_gap_frames"]))
        self.repository.replace_threshold_suggestions(video_id, selected, merged)
        cache_version = f"{profile_record['version']}:{hashlib.sha256(json.dumps(profile, sort_keys=True).encode()).hexdigest()[:12]}"
        self.repository.update_video(video_id, threshold_cache_version=cache_version, processing_status="threshold_suggestion_ready")
        return self.repository.list_suggestions("threshold_suggestions", video_id)

    @staticmethod
    def _candidate(track_id: int, record: dict[str, Any], label: str, confidence: float, conditions: list[str], scores: dict[str, float]) -> dict[str, Any]:
        key_data = f"{track_id}:{record['start_frame']}:{record['end_frame']}:{label}:{conditions}"
        return {
            "track_id": track_id, "start_frame": record["start_frame"], "end_frame": record["end_frame"],
            "suggested_label": label, "confidence": confidence,
            "triggered_conditions_json": json.dumps(conditions),
            "supporting_features_json": json.dumps(scores, sort_keys=True),
            "quality_status": record["quality"]["status"], "review_status": "pending",
            "artifact_key": hashlib.sha256(key_data.encode()).hexdigest(),
        }

    @staticmethod
    def _merge_candidates(candidates: list[dict[str, Any]], gap: int) -> list[dict[str, Any]]:
        merged: list[dict[str, Any]] = []
        for candidate in sorted(candidates, key=lambda item: (item["track_id"], item["suggested_label"], item["start_frame"])):
            if merged and merged[-1]["track_id"] == candidate["track_id"] and merged[-1]["suggested_label"] == candidate["suggested_label"] and candidate["start_frame"] <= merged[-1]["end_frame"] + gap + 1:
                merged[-1]["end_frame"] = max(merged[-1]["end_frame"], candidate["end_frame"])
                merged[-1]["confidence"] = max(merged[-1]["confidence"], candidate["confidence"])
                merged[-1]["artifact_key"] = hashlib.sha256(f"{merged[-1]['artifact_key']}:{candidate['artifact_key']}".encode()).hexdigest()
            else:
                merged.append(dict(candidate))
        return merged

    def save_profile(self, project_id: str, name: str, config: dict[str, Any], profile_id: str | None = None) -> dict[str, Any]:
        self._validate_profile(config)
        if profile_id is None:
            version = f"v{len(self.repository.list_threshold_profiles(project_id)) + 1}"
            return self.repository.create_threshold_profile(project_id, name, version, config)
        profile = self.repository.get_threshold_profile(profile_id)
        if profile["project_id"] != project_id:
            raise VideoValidationError("Threshold profile belongs to another project")
        self.repository.execute(
            "UPDATE threshold_profiles SET name=?,config_json=?,version=version || '.1',updated_at=CURRENT_TIMESTAMP WHERE threshold_profile_id=?",
            (name, json.dumps(config, sort_keys=True), profile_id),
        )
        self.repository.execute(
            "UPDATE videos SET threshold_cache_version=NULL,updated_at=CURRENT_TIMESTAMP WHERE project_id=?",
            (project_id,),
        )
        return self.repository.get_threshold_profile(profile_id)

    @staticmethod
    def _validate_profile(config: dict[str, Any]) -> None:
        required = {"transforms", "fall", "running", "quality", "merge_gap_frames"}
        if not required.issubset(config):
            raise VideoValidationError("Threshold profile is missing required sections")
        for name, bounds in config["transforms"].items():
            if len(bounds) != 2 or float(bounds[1]) <= float(bounds[0]):
                raise VideoValidationError(f"Invalid transform range for {name}")

    def restore_default_profile(self, project_id: str) -> dict[str, Any]:
        return self.repository.create_threshold_profile(
            project_id, "Restored Default", f"v{len(self.repository.list_threshold_profiles(project_id)) + 1}",
            threshold_profile_config(),
        )
