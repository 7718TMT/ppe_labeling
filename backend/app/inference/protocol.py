from pathlib import Path
from typing import Protocol

from backend.app.domain.models import BoundingBox


class Detector(Protocol):
    def detect(self, image_path: Path) -> list[BoundingBox]: ...

    def detect_image(self, image) -> list[BoundingBox]: ...
