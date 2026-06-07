from pathlib import Path

from fastapi import HTTPException

from backend.app.ml.yolo_detector import PpeDetector
from backend.app.services import storage


class LabelingService:
    def __init__(self, image_dir: Path, label_dir: Path, detector: PpeDetector) -> None:
        self.image_dir = image_dir
        self.label_dir = label_dir
        self.detector = detector

    def auto_label_all(self) -> int:
        processed = 0
        for image_path in storage.image_paths(self.image_dir):
            self.auto_label_one(image_path.name)
            processed += 1
        return processed

    def auto_label_one(self, filename: str) -> int:
        storage.validate_image_filename(filename)
        image_path = self.image_dir / filename
        if not image_path.exists():
            raise HTTPException(status_code=404, detail="Image not found")

        boxes = self.detector.detect(image_path)
        storage.save_labels(self.label_dir, filename, boxes)
        return len(boxes)
