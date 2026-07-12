from backend.app.domain.errors import ImageNotFoundError
from backend.app.inference.protocol import Detector
from backend.app.repositories.dataset import DatasetRepository


class LabelingService:
    def __init__(self, dataset: DatasetRepository, detector: Detector) -> None:
        self.dataset = dataset
        self.detector = detector

    def auto_label_all(self) -> int:
        self.dataset.ensure_unique_image_stems()
        processed = 0
        for image_path in self.dataset.image_paths():
            self.auto_label_one(image_path.name)
            processed += 1
        return processed

    def auto_label_one(self, filename: str) -> int:
        image_path = self.dataset.image_path_for(filename)
        if not image_path.exists():
            raise ImageNotFoundError("Image not found")
        self.dataset.ensure_unique_image_stem(filename)

        boxes = self.detector.detect(image_path)
        self.dataset.save_labels(filename, boxes)
        return len(boxes)
