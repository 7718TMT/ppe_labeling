import logging
from pathlib import Path

from backend.app.core.device import resolve_inference_device
from backend.app.domain.errors import ModelUnavailableError, UnreadableImageError
from backend.app.domain.geometry import clamp_box
from backend.app.domain.models import BoundingBox
from backend.app.inference.vest_detector import detect_vests


logger = logging.getLogger(__name__)


class PpeDetector:
    def __init__(
        self,
        model_path: Path,
        image_size: int = 640,
        confidence: float = 0.25,
        iou: float = 0.7,
        allowed_class_ids: set[int] | None = None,
        use_color_vest_fallback: bool = False,
        device: str = "auto",
    ) -> None:
        self.model_path = model_path
        self.image_size = image_size
        self.confidence = confidence
        self.iou = iou
        self.allowed_class_ids = allowed_class_ids or {0, 1, 2}
        self.use_color_vest_fallback = use_color_vest_fallback
        self.device = resolve_inference_device(device)
        self._model = None

    @property
    def model(self):
        from ultralytics import YOLO

        if self._model is None:
            if not self.model_path.exists():
                raise ModelUnavailableError(f"Model file not found: {self.model_path}")
            logger.info(
                "Loading PPE detector model",
                extra={"detector_type": "ppe", "model_path": str(self.model_path), "inference_device": self.device},
            )
            self._model = YOLO(str(self.model_path))
        return self._model

    def detect(self, image_path: Path) -> list[BoundingBox]:
        import cv2

        image = cv2.imread(str(image_path))
        if image is None:
            raise UnreadableImageError(f"Unreadable image: {image_path.name}")

        boxes: list[BoundingBox] = []
        humans: list[BoundingBox] = []
        helmets: list[BoundingBox] = []
        vests: list[BoundingBox] = []
        results = self.model(
            image_path,
            imgsz=self.image_size,
            conf=self.confidence,
            iou=self.iou,
            device=self.device,
            verbose=False,
        )
        for result in results:
            for index, cls_id in enumerate(result.boxes.cls.tolist()):
                class_id = int(cls_id)
                if class_id not in self.allowed_class_ids:
                    continue
                x_center, y_center, width, height = result.boxes.xywhn.tolist()[index]
                box = clamp_box(BoundingBox(class_id, x_center, y_center, width, height))
                boxes.append(box)
                if class_id == 0:
                    humans.append(box)
                elif class_id == 1:
                    helmets.append(box)
                elif class_id == 2:
                    vests.append(box)
        if self.use_color_vest_fallback and not vests:
            boxes.extend(detect_vests(image, humans, helmets))
        return boxes
