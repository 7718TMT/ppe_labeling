from pathlib import Path

from fastapi import HTTPException

from backend.app.models.schemas import BoundingBox
from backend.app.services.storage import clamp_box


class SafetySignDetector:
    def __init__(
        self,
        model_path: Path,
        prompts: list[str],
        image_size: int = 640,
        confidence: float = 0.15,
        iou: float = 0.7,
        temporary_class_id: int = 4,
        agnostic_nms: bool = True,
    ) -> None:
        self.model_path = model_path
        self.prompts = prompts
        self.image_size = image_size
        self.confidence = confidence
        self.iou = iou
        self.temporary_class_id = temporary_class_id
        self.agnostic_nms = agnostic_nms
        self._model = None

    @property
    def model(self):
        from ultralytics import YOLO

        if self._model is None:
            if not self.model_path.exists():
                raise HTTPException(status_code=500, detail=f"Model file not found: {self.model_path}")
            model = YOLO(str(self.model_path))
            if not hasattr(model, "set_classes"):
                raise HTTPException(
                    status_code=500,
                    detail="Loaded model does not support YOLO-World text prompts. Use a *-world*.pt model.",
                )
            model.set_classes(self.prompts)
            self._model = model
        return self._model

    def detect(self, image_path: Path) -> list[BoundingBox]:
        import cv2

        image = cv2.imread(str(image_path))
        if image is None:
            raise HTTPException(status_code=422, detail=f"Unreadable image: {image_path.name}")

        results = self.model(
            image_path,
            imgsz=self.image_size,
            conf=self.confidence,
            iou=self.iou,
            agnostic_nms=self.agnostic_nms,
            verbose=False,
        )

        boxes: list[BoundingBox] = []
        for result in results:
            for x_center, y_center, width, height in result.boxes.xywhn.tolist():
                boxes.append(
                    clamp_box(
                        BoundingBox(
                            class_id=self.temporary_class_id,
                            x_center=x_center,
                            y_center=y_center,
                            w=width,
                            h=height,
                        )
                    )
                )
        return boxes
