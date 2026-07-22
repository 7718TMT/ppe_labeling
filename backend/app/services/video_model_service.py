"""Trusted-local external model validation and inference-only suggestions."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

import numpy as np

from backend.app.core.device import resolve_inference_device
from backend.app.domain.errors import ModelCompatibilityError, VideoValidationError
from backend.app.domain.video import CANONICAL_FPS, FEATURE_SCHEMA_VERSION, HUMAN_LABELS
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_feature_service import VideoFeatureService
from backend.app.services.video_features import feature_columns
from backend.app.services.video_service import VideoService


class VideoModelService:
    """Load explicitly trusted packages and preserve versioned prediction provenance."""

    def __init__(
        self,
        repository: VideoRepository,
        storage: VideoStorageRepository,
        features: VideoFeatureService,
        inference_device: str = "auto",
    ) -> None:
        self.repository = repository
        self.storage = storage
        self.features = features
        self.inference_device = inference_device

    def import_model(
        self,
        project_id: str,
        filename: str,
        artifact: BinaryIO,
        manifest: dict[str, Any],
        trusted_local: bool,
    ) -> dict[str, Any]:
        self.repository.get_project(project_id)
        suffix = Path(filename).suffix.lower()
        adapter = "onnx" if suffix == ".onnx" else "joblib"
        if adapter == "joblib" and not trusted_local:
            raise VideoValidationError(
                "Pickle/joblib packages can execute code. Confirm this is a trusted local package before loading."
            )
        model_id = uuid4().hex
        path, digest = self.storage.copy_model_artifact(project_id, model_id, filename, artifact)
        errors = self.compatibility_errors(manifest)
        if not errors:
            try:
                self._load_artifact(path, adapter)
            except Exception as exc:
                errors.append(f"artifact_loading: {exc}")
        values = {
            "name": str(manifest.get("name", Path(filename).stem)),
            "version": str(manifest.get("version", "unversioned")),
            "artifact_path": str(path), "artifact_hash": digest, "adapter_type": adapter,
            "class_map_json": json.dumps(manifest.get("class_map", {}), sort_keys=True),
            "feature_schema_version": str(manifest.get("feature_schema_version", "")),
            "feature_columns_json": json.dumps(manifest.get("feature_columns", [])),
            "window_config_json": json.dumps({
                "length": manifest.get("window_length"), "stride": manifest.get("stride"),
                "canonical_fps": manifest.get("canonical_fps"),
            }),
            "compatibility_status": "compatible" if not errors else "incompatible",
            "compatibility_errors_json": json.dumps(errors),
            "metadata_json": json.dumps(manifest, sort_keys=True),
        }
        record = self.repository.create_external_model(project_id, model_id, values)
        if not errors:
            record = self.repository.activate_external_model(project_id, model_id)
        return record

    def list_models(self, project_id: str) -> list[dict[str, Any]]:
        return self.repository.list_external_models(project_id)

    def activate_model(self, project_id: str, model_id: str) -> dict[str, Any]:
        model = self.repository.get_external_model(model_id)
        if model["project_id"] != project_id:
            raise VideoValidationError("External model belongs to another project")
        if model["compatibility_status"] != "compatible":
            raise ModelCompatibilityError(
                "Model suggestions are unavailable because the configured model is incompatible."
            )
        if not Path(model["artifact_path"]).is_file():
            raise ModelCompatibilityError(
                "Model suggestions are temporarily unavailable."
            )
        return self.repository.activate_external_model(project_id, model_id)

    def deactivate_model(self, project_id: str, model_id: str) -> dict[str, Any]:
        return self.repository.deactivate_external_model(project_id, model_id)

    def queue_inference(self, project_id: str, video_id: str, model_id: str) -> dict[str, Any]:
        model = self.repository.get_external_model(model_id)
        if model["project_id"] != project_id:
            raise VideoValidationError("External model belongs to another project")
        if model["compatibility_status"] != "compatible":
            raise ModelCompatibilityError(
                "Model suggestions are unavailable because the configured model is incompatible."
            )
        if not model["is_active"]:
            raise ModelCompatibilityError(
                "Select this model as the project model before processing."
            )
        if not Path(model["artifact_path"]).is_file():
            raise ModelCompatibilityError(
                "Model suggestions are temporarily unavailable."
            )
        return VideoService(self.repository, self.storage).queue_pipeline(
            project_id,
            video_id,
            "model",
            90,
        )[0]

    @staticmethod
    def compatibility_errors(manifest: dict[str, Any]) -> list[str]:
        errors: list[str] = []
        class_map = manifest.get("class_map")
        names = set(class_map.keys()) if isinstance(class_map, dict) else set(class_map or [])
        if len(names) != 3 or names != set(HUMAN_LABELS):
            errors.append("class_map: expected exactly others, running, falling")
        if manifest.get("feature_schema_version") != FEATURE_SCHEMA_VERSION:
            errors.append(f"feature_schema_version: expected {FEATURE_SCHEMA_VERSION}, got {manifest.get('feature_schema_version')}")
        expected_columns = feature_columns()
        if manifest.get("feature_columns") != expected_columns:
            errors.append("feature_columns: missing, extra, or incorrect column order")
        if int(manifest.get("window_length", -1)) != 60:
            errors.append(f"window_length: expected 60, got {manifest.get('window_length')}")
        if int(manifest.get("stride", -1)) != 12:
            errors.append(f"stride: expected 12, got {manifest.get('stride')}")
        if float(manifest.get("canonical_fps", -1)) != CANONICAL_FPS:
            errors.append(f"canonical_fps: expected 24, got {manifest.get('canonical_fps')}")
        return errors

    def run_inference(self, video_id: str, model_id: str) -> list[dict[str, Any]]:
        model = self.repository.get_external_model(model_id)
        video = self.repository.get_video(video_id)
        if video["project_id"] != model["project_id"]:
            raise VideoValidationError("External model and video belong to different projects")
        if model["compatibility_status"] != "compatible":
            raise ModelCompatibilityError("Model is incompatible: " + "; ".join(model["compatibility_errors"]))
        records = self.features.feature_range(video_id)
        if not records:
            self.features.extract_features(video_id)
            records = self.features.feature_range(video_id)
        if not records:
            self.repository.replace_model_predictions(model_id, video_id, [], [])
            self.repository.update_video(video_id, processing_status="model_suggestion_ready")
            return []
        columns = model["feature_columns"]
        if model["metadata"].get("preprocessing") == "behavior_preprocess_v1":
            matrix = self._behavior_matrix(records)
        else:
            matrix = np.asarray([[record["raw"][column] for column in columns] for record in records], dtype=np.float32)
        probabilities = self._predict(Path(model["artifact_path"]), model["adapter_type"], matrix)
        class_map = model["class_map"]
        ordered_classes = (
            [name for name, _index in sorted(class_map.items(), key=lambda item: int(item[1]))]
            if isinstance(class_map, dict)
            else list(class_map)
        )
        indexes = {name: ordered_classes.index(name) for name in HUMAN_LABELS}
        predictions: list[dict[str, Any]] = []
        scored_windows: list[tuple[dict[str, Any], dict[str, float]]] = []
        inference = model["metadata"].get("inference", {})
        minimum = float(inference.get("minimum_probability", 0.65))
        for record, row in zip(records, probabilities, strict=True):
            values = {name: float(row[indexes[name]]) for name in HUMAN_LABELS}
            label = max(values, key=values.get)
            confidence = values[label]
            predictions.append({
                "window_id": record["window_id"],
                "others_probability": values["others"], "running_probability": values["running"],
                "falling_probability": values["falling"], "predicted_label": label, "confidence": confidence,
            })
            scored_windows.append((record, values))

        # Keep the persisted window predictions raw for inspection. Event
        # generation uses a centered three-window probability mean, which
        # suppresses isolated class flips without hiding the model output.
        candidates: list[dict[str, Any]] = []
        by_track: dict[int, list[tuple[dict[str, Any], dict[str, float]]]] = {}
        for record, values in scored_windows:
            by_track.setdefault(int(record["track_id"]), []).append((record, values))
        for track_windows in by_track.values():
            track_windows.sort(key=lambda item: int(item[0]["start_frame"]))
            for position, (record, _raw_values) in enumerate(track_windows):
                neighborhood = track_windows[
                    max(0, position - 1):min(len(track_windows), position + 2)
                ]
                values = {
                    name: sum(item[1][name] for item in neighborhood)
                    / len(neighborhood)
                    for name in HUMAN_LABELS
                }
                label = max(values, key=values.get)
                confidence = values[label]
                # Attribute overlapping windows by midpoint so consecutive
                # classes form one non-overlapping per-track event timeline.
                start_frame = int(record["start_frame"])
                end_frame = int(record["end_frame"])
                center = (start_frame + end_frame) / 2
                if position > 0:
                    previous = track_windows[position - 1][0]
                    previous_center = (
                        int(previous["start_frame"])
                        + int(previous["end_frame"])
                    ) / 2
                    start_frame = int((previous_center + center) // 2) + 1
                if position + 1 < len(track_windows):
                    following = track_windows[position + 1][0]
                    following_center = (
                        int(following["start_frame"])
                        + int(following["end_frame"])
                    ) / 2
                    end_frame = int((center + following_center) // 2)
                if (
                    label in {"running", "falling"}
                    and confidence >= minimum
                    and record["quality"]["status"] != "low_quality"
                ):
                    candidates.append({
                        "track_id": record["track_id"],
                        "start_frame": start_frame,
                        "end_frame": end_frame,
                        "suggested_label": label,
                        "confidence": confidence,
                        "source_window_ids_json": json.dumps(
                            [record["window_id"]]
                        ),
                        "probabilities_json": json.dumps(values),
                        "merge_config_json": json.dumps(
                            inference, sort_keys=True
                        ),
                        "review_status": "pending",
                    })
        suggestions = self._merge(candidates, int(inference.get("maximum_merge_gap", 12)))
        self.repository.replace_model_predictions(model_id, video_id, predictions, suggestions)
        self.repository.update_video(video_id, processing_status="model_suggestion_ready")
        return self.repository.list_suggestions("model_suggestions", video_id)

    @staticmethod
    def _load_artifact(path: Path, adapter: str) -> Any:
        if adapter == "joblib":
            import joblib

            model = joblib.load(path)
            if not hasattr(model, "predict_proba"):
                raise ModelCompatibilityError("Trusted joblib model must expose predict_proba")
            return model
        import onnxruntime as ort

        return ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])

    def _predict(self, path: Path, adapter: str, matrix: np.ndarray) -> np.ndarray:
        model = self._load_artifact(path, adapter)
        if adapter == "joblib":
            booster = getattr(model, "get_booster", lambda: None)()
            if booster is not None:
                booster.set_param({"device": resolve_inference_device(self.inference_device)})
            result = np.asarray(model.predict_proba(matrix), dtype=np.float32)
        else:
            input_name = model.get_inputs()[0].name
            result = np.asarray(model.run(None, {input_name: matrix})[0], dtype=np.float32)
        if result.ndim != 2 or result.shape != (len(matrix), 3):
            raise ModelCompatibilityError(f"Inference returned {result.shape}; expected ({len(matrix)}, 3)")
        return result

    @staticmethod
    def _behavior_matrix(records: list[dict[str, Any]]) -> np.ndarray:
        """Reproduce the numeric preprocessing used by behavior_preprocess.ipynb."""

        excluded = {"track_gap_count", "valid_frame_ratio"}
        square_root = {
            "ground_speed_mean", "ground_speed_max", "combined_speed_mean",
            "combined_speed_std", "body_acceleration_max",
        }
        double_log = {"skeleton_spread_ratio_max", "skeleton_spread_ratio_mean"}
        columns = [name for name in feature_columns() if name not in excluded]
        rows: list[list[float]] = []
        for record in records:
            values: list[float] = []
            for name in columns:
                value = float(record["raw"][name])
                if name in square_root:
                    value = float(np.sqrt(max(0.0, value)))
                elif name in double_log:
                    value = float(np.log1p(np.log1p(max(0.0, value))))
                values.append(value)
            rows.append(values)
        return np.asarray(rows, dtype=np.float32)

    @staticmethod
    def _merge(candidates: list[dict[str, Any]], gap: int) -> list[dict[str, Any]]:
        priority = {"running": 1, "falling": 2}
        ordered = sorted(candidates, key=lambda item: (item["track_id"], item["start_frame"], -priority[item["suggested_label"]]))
        merged: list[dict[str, Any]] = []
        for candidate in ordered:
            if merged and merged[-1]["track_id"] == candidate["track_id"] and merged[-1]["suggested_label"] == candidate["suggested_label"] and candidate["start_frame"] <= merged[-1]["end_frame"] + gap + 1:
                merged[-1]["end_frame"] = max(merged[-1]["end_frame"], candidate["end_frame"])
                merged[-1]["confidence"] = max(merged[-1]["confidence"], candidate["confidence"])
                ids = json.loads(merged[-1]["source_window_ids_json"]) + json.loads(candidate["source_window_ids_json"])
                merged[-1]["source_window_ids_json"] = json.dumps(ids)
            else:
                merged.append(dict(candidate))
        return merged
