from backend.app.domain.errors import ImageNotFoundError, UnreadableImageError
from backend.app.repositories.dataset import DatasetRepository


CLASS_COLORS = [
    (255, 0, 0),
    (0, 0, 255),
    (0, 255, 0),
    (0, 255, 255),
    (248, 189, 56),
    (255, 0, 255),
    (255, 128, 0),
    (128, 0, 255),
]


class VisualizationService:
    def __init__(
        self,
        dataset: DatasetRepository,
        class_names: dict[int, str],
    ) -> None:
        self.dataset = dataset
        self.class_names = class_names

    def generate_all(self) -> int:
        self.dataset.ensure_unique_image_stems()
        generated = 0
        for image_path in self.dataset.image_paths():
            label_path = self.dataset.label_path_for(image_path.name)
            if not label_path.exists():
                continue
            self.generate_one(image_path.name)
            generated += 1
        return generated

    def generate_one(self, filename: str) -> None:
        import cv2

        image_path = self.dataset.image_path_for(filename)
        if not image_path.exists():
            raise ImageNotFoundError("Image not found")
        self.dataset.ensure_unique_image_stem(filename)

        image = cv2.imread(str(image_path))
        if image is None:
            raise UnreadableImageError(f"Unreadable image: {filename}")

        height, width, _ = image.shape
        for box in self.dataset.read_labels(filename):
            x1 = int((box.x_center - box.w / 2) * width)
            y1 = int((box.y_center - box.h / 2) * height)
            x2 = int((box.x_center + box.w / 2) * width)
            y2 = int((box.y_center + box.h / 2) * height)
            x1, y1 = max(0, x1), max(0, y1)
            x2, y2 = min(width - 1, x2), min(height - 1, y2)

            color = color_for_class(box.class_id)
            cv2.rectangle(image, (x1, y1), (x2, y2), color, 3)
            cv2.putText(
                image,
                f"{box.class_id}: {self.class_names.get(box.class_id, 'Unknown')}",
                (x1, max(y1 - 10, 20)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2,
            )

        output_path = self.dataset.visualization_path_for(filename)
        cv2.imwrite(str(output_path), image)


def color_for_class(class_id: int) -> tuple[int, int, int]:
    if class_id < len(CLASS_COLORS):
        return CLASS_COLORS[class_id]
    return (
        (37 * class_id + 80) % 256,
        (67 * class_id + 140) % 256,
        (97 * class_id + 200) % 256,
    )
