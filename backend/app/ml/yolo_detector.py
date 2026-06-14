from pathlib import Path

from fastapi import HTTPException

from backend.app.core.device import resolve_inference_device
from backend.app.models.schemas import BoundingBox
from backend.app.services.storage import clamp_box


class PpeDetector:
    def __init__(
        self,
        model_path: Path,
        image_size: int = 640,
        confidence: float = 0.25,
        iou: float = 0.7,
        use_color_vest_fallback: bool = False,
        device: str = "auto",
    ) -> None:
        self.model_path = model_path
        self.image_size = image_size
        self.confidence = confidence
        self.iou = iou
        self.use_color_vest_fallback = use_color_vest_fallback
        self.device = resolve_inference_device(device)
        self._model = None

    @property
    def model(self):
        from ultralytics import YOLO

        if self._model is None:
            if not self.model_path.exists():
                raise HTTPException(status_code=500, detail=f"Model file not found: {self.model_path}")
            self._model = YOLO(str(self.model_path))
        return self._model

    def detect(self, image_path: Path) -> list[BoundingBox]:
        import cv2

        from backend.app.ml.vest_detector import detect_vests

        image = cv2.imread(str(image_path))
        if image is None:
            raise HTTPException(status_code=422, detail=f"Unreadable image: {image_path.name}")

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
            xywhn_list = result.boxes.xywhn.tolist()
            cls_list = result.boxes.cls.tolist()
            for index, cls_id in enumerate(cls_list):
                class_id = int(cls_id)
                if class_id not in (0, 1, 2):
                    continue
                x_center, y_center, width, height = xywhn_list[index]
                box = clamp_box(
                    BoundingBox(
                        class_id=class_id,
                        x_center=x_center,
                        y_center=y_center,
                        w=width,
                        h=height,
                    )
                )
                if class_id == 0:
                    humans.append(box)
                elif class_id == 1:
                    helmets.append(box)
                else:
                    vests.append(box)

        if self.use_color_vest_fallback and not vests:
            vests = detect_vests(image, humans, helmets)

        return [*helmets, *humans, *vests]
