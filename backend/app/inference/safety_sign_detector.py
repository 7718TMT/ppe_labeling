import logging
from pathlib import Path

from backend.app.core.device import resolve_inference_device
from backend.app.domain.errors import ModelUnavailableError, UnreadableImageError
from backend.app.domain.geometry import clamp_box
from backend.app.domain.models import BoundingBox


logger = logging.getLogger(__name__)


class SafetySignDetector:
    def __init__(
        self,
        model_path: Path,
        allowed_class_ids: set[int],
        image_size: int = 640,
        confidence: float = 0.15,
        iou: float = 0.7,
        agnostic_nms: bool = False,
        device: str = "auto",
    ) -> None:
        self.model_path = model_path
        self.allowed_class_ids = allowed_class_ids
        self.image_size = image_size
        self.confidence = confidence
        self.iou = iou
        self.agnostic_nms = agnostic_nms
        self.device = resolve_inference_device(device)
        self._model = None

    @property
    def model(self):
        from ultralytics import YOLO

        if self._model is None:
            if not self.model_path.exists():
                raise ModelUnavailableError(f"Model file not found: {self.model_path}")
            logger.info(
                "Loading safety-sign detector model",
                extra={"detector_type": "safety_signs", "model_path": str(self.model_path), "inference_device": self.device},
            )
            self._model = YOLO(str(self.model_path))
        return self._model

    def detect(self, image_path: Path) -> list[BoundingBox]:
        import cv2

        image = cv2.imread(str(image_path))
        if image is None:
            raise UnreadableImageError(f"Unreadable image: {image_path.name}")
        results = self.model(
            image_path,
            imgsz=self.image_size,
            conf=self.confidence,
            iou=self.iou,
            agnostic_nms=self.agnostic_nms,
            device=self.device,
            verbose=False,
        )
        boxes: list[BoundingBox] = []
        for result in results:
            for class_id_value, (x_center, y_center, width, height) in zip(
                result.boxes.cls.tolist(), result.boxes.xywhn.tolist(), strict=True
            ):
                class_id = int(class_id_value)
                if class_id in self.allowed_class_ids:
                    boxes.append(clamp_box(BoundingBox(class_id, x_center, y_center, width, height)))
        return boxes
