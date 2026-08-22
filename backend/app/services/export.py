"""Filesystem-only dataset ZIP export workflow."""

import logging
import tempfile
from pathlib import Path
from zipfile import ZIP_STORED, ZipFile

from backend.app.domain.models import ExportResult
from backend.app.repositories.dataset import DatasetRepository


logger = logging.getLogger(__name__)


class DatasetExportService:
    """Builds task ZIP artifacts without reading approval metadata."""

    def __init__(self, task_id: str, dataset: DatasetRepository) -> None:
        self.task_id = task_id
        self.dataset = dataset

    def export_image(self, filename: str) -> ExportResult:
        return self.export_images([filename], f"{Path(filename).stem}_dataset.zip")

    def export_all(self) -> ExportResult:
        return self.export_images([path.name for path in self.dataset.image_paths()], f"{self.task_id}_dataset.zip")

    def export_images(self, filenames: list[str], download_name: str) -> ExportResult:
        temporary_file = tempfile.NamedTemporaryFile(suffix=".zip", delete=False)
        try:
            with ZipFile(temporary_file, mode="w", compression=ZIP_STORED) as zip_file:
                for filename in filenames:
                    self.dataset.add_image_and_label_to_zip(zip_file, filename)
            temporary_file.close()
            result = ExportResult(archive_path=Path(temporary_file.name), download_name=download_name)
            logger.info("Created dataset export", extra={"task_id": self.task_id, "image_count": len(filenames)})
            return result
        except Exception:
            temporary_file.close()
            Path(temporary_file.name).unlink(missing_ok=True)
            raise
