"""Persistent, read-only inference workspace for PPE and safety-sign media."""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from imageio_ffmpeg import get_ffmpeg_exe

from backend.app.core.config import TaskProfile
from backend.app.domain.errors import ImageNotFoundError, InvalidFilenameError, VideoValidationError
from backend.app.domain.models import BoundingBox
from backend.app.inference.protocol import Detector


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}
# OpenCV uses BGR. These values correspond to the UI palette:
# #2dd4bf, #3b82f6, #f59e0b, #ef4444, and #a855f7.
COLORS = ((191, 212, 45), (246, 130, 59), (11, 158, 245), (68, 68, 239), (247, 85, 168))


class ImageInferenceService:
    def __init__(self, profile: TaskProfile, storage_root: Path, detector: Detector) -> None:
        self.profile = profile
        self.root = storage_root / profile.id
        self.detector = detector
        for directory in (self.source_dir, self.result_dir, self.metadata_dir):
            directory.mkdir(parents=True, exist_ok=True)

    @property
    def source_dir(self) -> Path:
        return self.root / "source"

    @property
    def result_dir(self) -> Path:
        return self.root / "result"

    @property
    def metadata_dir(self) -> Path:
        return self.root / "items"

    def list_items(self) -> list[dict[str, object]]:
        items: list[dict[str, object]] = []
        for path in self.metadata_dir.glob("*.json"):
            try:
                items.append(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError):
                continue
        return [
            self._public_item(item)
            for item in sorted(items, key=lambda item: str(item["created_at"]), reverse=True)
        ]

    def infer(self, filename: str, content: bytes) -> dict[str, object]:
        safe_name = self._validate_filename(filename)
        suffix = Path(safe_name).suffix.lower()
        media_type = "image" if suffix in IMAGE_EXTENSIONS else "video"
        item_id = uuid4().hex
        source_name = f"{item_id}{suffix}"
        result_suffix = ".jpg" if media_type == "image" else ".mp4"
        result_name = f"{item_id}{result_suffix}"
        source_path = self.source_dir / source_name
        result_path = self.result_dir / result_name
        source_path.write_bytes(content)

        try:
            detections = (
                self._infer_image(source_path, result_path)
                if media_type == "image"
                else self._infer_video(source_path, result_path)
            )
        except Exception:
            source_path.unlink(missing_ok=True)
            result_path.unlink(missing_ok=True)
            raise

        item: dict[str, object] = {
            "id": item_id,
            "task_id": self.profile.id,
            "filename": safe_name,
            "media_type": media_type,
            "source_url": f"/api/v1/tasks/{self.profile.id}/inference/{item_id}/source",
            "result_url": f"/api/v1/tasks/{self.profile.id}/inference/{item_id}/result",
            "detections": detections,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "source_name": source_name,
            "result_name": result_name,
            "render_version": 2,
        }
        self.metadata_dir.joinpath(f"{item_id}.json").write_text(json.dumps(item), encoding="utf-8")
        return self._public_item(item)

    def media_path(self, item_id: str, variant: str) -> Path:
        item = self._read_item(item_id)
        key = "source_name" if variant == "source" else "result_name"
        base = self.source_dir if variant == "source" else self.result_dir
        path = base / str(item[key])
        if not path.exists():
            raise ImageNotFoundError("Inference media not found")
        return path

    def delete(self, item_id: str) -> None:
        item = self._read_item(item_id)
        self.source_dir.joinpath(str(item["source_name"])).unlink(missing_ok=True)
        self.result_dir.joinpath(str(item["result_name"])).unlink(missing_ok=True)
        self.metadata_dir.joinpath(f"{item_id}.json").unlink(missing_ok=True)

    def rerender(self, item_id: str) -> dict[str, object]:
        """Rebuild a derived result while preserving the uploaded source."""

        item = self._read_item(item_id)
        source_path = self.source_dir / str(item["source_name"])
        result_path = self.result_dir / str(item["result_name"])
        if not source_path.exists():
            raise ImageNotFoundError("Inference source media not found")
        temporary_result = result_path.with_name(f"{result_path.stem}.updated{result_path.suffix}")
        try:
            detections = (
                self._infer_image(source_path, temporary_result)
                if item["media_type"] == "image"
                else self._infer_video(source_path, temporary_result)
            )
            temporary_result.replace(result_path)
        finally:
            temporary_result.unlink(missing_ok=True)
        item["detections"] = detections
        item["render_version"] = 2
        self.metadata_dir.joinpath(f"{item_id}.json").write_text(json.dumps(item), encoding="utf-8")
        return self._public_item(item)

    def _infer_image(self, source_path: Path, result_path: Path) -> int:
        import cv2

        image = cv2.imread(str(source_path))
        if image is None:
            raise VideoValidationError("The uploaded image cannot be decoded")
        boxes = self.detector.detect_image(image)
        rendered = self._draw_boxes(image, boxes)
        if not cv2.imwrite(str(result_path), rendered):
            raise VideoValidationError("Could not save the inference result")
        return len(boxes)

    def _infer_video(self, source_path: Path, result_path: Path) -> int:
        import cv2

        capture = cv2.VideoCapture(str(source_path))
        if not capture.isOpened():
            raise VideoValidationError("The uploaded video cannot be decoded")
        width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = capture.get(cv2.CAP_PROP_FPS) or 25.0
        temporary = result_path.with_suffix(".rendering.mp4")
        writer = cv2.VideoWriter(str(temporary), cv2.VideoWriter_fourcc(*"mp4v"), fps, (width, height))
        if not writer.isOpened():
            capture.release()
            raise VideoValidationError("Could not create the inference video")
        total = 0
        try:
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                boxes = self.detector.detect_image(frame)
                total += len(boxes)
                writer.write(self._draw_boxes(frame, boxes))
        finally:
            capture.release()
            writer.release()
        if not temporary.exists() or temporary.stat().st_size == 0:
            raise VideoValidationError("The uploaded video contains no readable frames")
        command = [
            get_ffmpeg_exe(), "-y", "-i", str(temporary), "-i", str(source_path),
            "-map", "0:v:0", "-map", "1:a?", "-c:v", "libx264", "-preset", "veryfast",
            "-crf", "20", "-pix_fmt", "yuv420p", "-c:a", "aac", "-movflags", "+faststart",
            str(result_path),
        ]
        try:
            completed = subprocess.run(command, capture_output=True, text=True, check=False)
        finally:
            temporary.unlink(missing_ok=True)
        if completed.returncode != 0 or not result_path.exists() or result_path.stat().st_size == 0:
            raise VideoValidationError("Could not encode a browser-compatible inference video")
        return total

    def _draw_boxes(self, image, boxes: list[BoundingBox]):
        import cv2

        height, width = image.shape[:2]
        for box in boxes:
            left = int((box.x_center - box.w / 2) * width)
            top = int((box.y_center - box.h / 2) * height)
            right = int((box.x_center + box.w / 2) * width)
            bottom = int((box.y_center + box.h / 2) * height)
            color = COLORS[box.class_id % len(COLORS)]
            cv2.rectangle(image, (left, top), (right, bottom), color, 2)
        return image

    def _read_item(self, item_id: str) -> dict[str, object]:
        if not item_id.isalnum():
            raise InvalidFilenameError("Invalid inference item")
        path = self.metadata_dir / f"{item_id}.json"
        if not path.exists():
            raise ImageNotFoundError("Inference item not found")
        return json.loads(path.read_text(encoding="utf-8"))

    @staticmethod
    def _public_item(item: dict[str, object]) -> dict[str, object]:
        return {
            key: value
            for key, value in item.items()
            if key not in {"source_name", "result_name", "render_version"}
        }

    @staticmethod
    def _validate_filename(filename: str) -> str:
        safe_name = Path(filename).name
        if not safe_name or safe_name != filename or "\\" in filename or "/" in filename:
            raise InvalidFilenameError("Invalid filename")
        if Path(safe_name).suffix.lower() not in IMAGE_EXTENSIONS | VIDEO_EXTENSIONS:
            raise VideoValidationError("Upload a JPG, PNG, WEBP, MP4, MOV, AVI, MKV, or WEBM file")
        return safe_name
