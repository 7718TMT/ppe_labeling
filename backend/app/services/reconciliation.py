"""Maintenance workflow for filesystem-backed datasets and approval metadata."""

import logging

from backend.app.domain.models import ReconciliationReport
from backend.app.repositories.approvals import ApprovalRepository
from backend.app.repositories.dataset import DatasetRepository


logger = logging.getLogger(__name__)


class ApprovalReconciliationService:
    """Find and optionally remove approval rows for images no longer on disk."""

    def __init__(
        self,
        task_id: str,
        dataset: DatasetRepository,
        approvals: ApprovalRepository,
    ) -> None:
        self.task_id = task_id
        self.dataset = dataset
        self.approvals = approvals

    def run(self, remove: bool = False) -> ReconciliationReport:
        stale_filenames = self.approvals.stale_filenames(self.task_id, self.dataset.image_filenames())
        removed_filenames: tuple[str, ...] = ()
        if remove and stale_filenames:
            self.approvals.delete_filenames(self.task_id, stale_filenames)
            removed_filenames = stale_filenames
            logger.info(
                "Removed stale approval metadata",
                extra={"task_id": self.task_id, "filenames": stale_filenames},
            )
        return ReconciliationReport(
            task_id=self.task_id,
            stale_filenames=stale_filenames,
            removed_filenames=removed_filenames,
        )
