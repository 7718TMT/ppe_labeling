import logging
from dataclasses import replace
from pathlib import Path

from backend.app.domain.errors import FilesystemOperationError, ImageNotFoundError, InvalidClassError, PartialOperationError
from backend.app.domain.models import (
    BoundingBox,
    DeleteImageResult,
    ImageRecord,
    ReconciliationReport,
    RenameDatasetResult,
)
from backend.app.inference.protocol import Detector
from backend.app.repositories.approvals import ApprovalRepository
from backend.app.repositories.dataset import DatasetRepository
from backend.app.services.labeling import LabelingService
from backend.app.services.reconciliation import ApprovalReconciliationService
from backend.app.services.visualization import VisualizationService


logger = logging.getLogger(__name__)


class AnnotationService:
    """Coordinates the shared filesystem-backed image annotation workflow."""

    def __init__(
        self,
        task_id: str,
        dataset: DatasetRepository,
        approvals: ApprovalRepository,
        detector: Detector | None,
        class_names: dict[int, str],
    ) -> None:
        self.task_id = task_id
        self.dataset = dataset
        self.approvals = approvals
        self.detector = detector
        self.visualization = VisualizationService(dataset, class_names)
        self.reconciliation = ApprovalReconciliationService(task_id, dataset, approvals)
        self.allowed_class_ids = set(class_names)

    def list_images(self, media_prefix: str) -> list[ImageRecord]:
        approved = self.approvals.approved_filenames(self.task_id)
        return [
            ImageRecord(
                name=image.name,
                has_label=image.has_label,
                is_approved=image.name in approved,
                image_url=f"{media_prefix}/images/{image.name}",
                visualization_url=(f"{media_prefix}/visualizations/verified_{Path(image.name).stem}.jpg" if image.has_visualization else None),
            )
            for image in self.dataset.list_images()
        ]

    def upload_images(self, files: list[tuple[str, bytes]]) -> int:
        for filename, content in files:
            self.dataset.save_uploaded_image(filename, content)
        return len(files)

    def read_labels(self, filename: str) -> list[BoundingBox]:
        if not self.dataset.image_path_for(filename).exists():
            return []
        return self.dataset.read_labels(filename)

    def save_labels(self, filename: str, boxes: list[BoundingBox]) -> None:
        invalid_ids = sorted({box.class_id for box in boxes if box.class_id not in self.allowed_class_ids})
        if invalid_ids:
            allowed = ", ".join(str(class_id) for class_id in sorted(self.allowed_class_ids))
            invalid = ", ".join(str(class_id) for class_id in invalid_ids)
            raise InvalidClassError(f"Invalid class ID(s): {invalid}. Allowed class IDs: {allowed}")
        if not self.dataset.image_path_for(filename).exists():
            raise ImageNotFoundError("Image not found")
        self.dataset.save_labels(filename, boxes)

    def set_approval(self, filename: str, is_approved: bool) -> None:
        image_path = self.dataset.image_path_for(filename)
        if is_approved and not image_path.exists():
            raise ImageNotFoundError("Image not found")
        self.approvals.set_approval(self.task_id, filename, is_approved)

    def delete_image(self, filename: str) -> DeleteImageResult:
        if not self.dataset.image_path_for(filename).exists():
            self.approvals.delete_approval(self.task_id, filename)
            return DeleteImageResult(filename=filename, filesystem_completed=True, approval_cleanup_completed=True)
        try:
            result = self.dataset.delete_image_artifacts(filename)
        except FilesystemOperationError as exc:
            logger.exception("Filesystem deletion failed", extra={"task_id": self.task_id, "image_filename": filename})
            raise PartialOperationError("Image deletion did not complete", exc.result) from exc
        try:
            self.approvals.delete_approval(self.task_id, filename)
        except Exception as exc:
            result = replace(
                result,
                reconciliation_required=True,
                warnings=("Filesystem deletion completed but approval cleanup failed.",),
            )
            logger.exception("Approval cleanup failed after image deletion", extra={"task_id": self.task_id, "image_filename": filename})
            raise PartialOperationError("Image deleted but approval reconciliation is required", result) from exc
        result = replace(result, approval_cleanup_completed=True)
        logger.info("Deleted image artifacts and approval metadata", extra={"task_id": self.task_id, "image_filename": filename})
        return result

    def rename_dataset_sequential(self) -> RenameDatasetResult:
        try:
            result = self.dataset.rename_dataset_sequential()
        except FilesystemOperationError as exc:
            logger.exception("Filesystem rename failed", extra={"task_id": self.task_id})
            raise PartialOperationError("Dataset rename did not complete", exc.result) from exc
        try:
            remap_removed = self.approvals.remap_filenames(self.task_id, result.filename_map)
        except Exception as exc:
            result = replace(
                result,
                reconciliation_required=True,
                warnings=("Filesystem rename completed but approval remapping failed.",),
            )
            logger.exception("Approval remapping failed after dataset rename", extra={"task_id": self.task_id})
            raise PartialOperationError("Dataset renamed but approval reconciliation is required", result) from exc
        try:
            reconciliation = self.reconcile_approvals(remove=True)
        except Exception as exc:
            result = replace(
                result,
                approvals_remapped=True,
                reconciliation_required=True,
                warnings=("Approval remapping completed but stale approval cleanup failed.",),
            )
            logger.exception("Stale approval cleanup failed after dataset rename", extra={"task_id": self.task_id})
            raise PartialOperationError("Dataset renamed but approval reconciliation is required", result) from exc
        removed_filenames = tuple(sorted(set(remap_removed).union(reconciliation.removed_filenames)))
        warnings = tuple(f"Removed stale approval metadata: {name}" for name in removed_filenames)
        result = replace(result, approvals_remapped=True, warnings=warnings)
        logger.info(
            "Renamed dataset and remapped approval metadata",
            extra={"task_id": self.task_id, "renamed_count": result.count, "stale_approval_count": len(removed_filenames)},
        )
        return result

    def auto_label_one(self, filename: str) -> int:
        return self._labeling_service().auto_label_one(filename)

    def auto_label_all(self) -> int:
        return self._labeling_service().auto_label_all()

    def generate_visualizations(self) -> int:
        return self.visualization.generate_all()

    def reconcile_approvals(self, remove: bool = False) -> ReconciliationReport:
        return self.reconciliation.run(remove)

    def _labeling_service(self) -> LabelingService:
        if self.detector is None:
            raise RuntimeError("An inference-enabled annotation service is required for auto-labeling")
        return LabelingService(self.dataset, self.detector)
