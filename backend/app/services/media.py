"""Filesystem-only media access for task-scoped image and visualization responses."""

from pathlib import Path

from backend.app.repositories.dataset import DatasetRepository


class MediaService:
    """Resolves safe media paths without reading approval metadata."""

    def __init__(self, dataset: DatasetRepository) -> None:
        self.dataset = dataset

    def image_path(self, filename: str) -> Path:
        return self.dataset.image_path_for(filename)

    def visualization_path(self, filename: str) -> Path:
        return self.dataset.visualization_file_path(filename)
