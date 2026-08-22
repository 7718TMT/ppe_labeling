from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class BoundingBox:
    class_id: int
    x_center: float
    y_center: float
    w: float
    h: float


@dataclass(frozen=True)
class DatasetImage:
    name: str
    has_label: bool
    has_visualization: bool


@dataclass(frozen=True)
class ImageRecord:
    name: str
    has_label: bool
    is_approved: bool
    image_url: str
    visualization_url: str | None


@dataclass(frozen=True)
class TaskDefinition:
    id: str
    name: str
    class_names: dict[int, str]
    temporary_class_id: int | None = None


@dataclass(frozen=True)
class DeleteImageResult:
    filename: str
    filesystem_completed: bool
    approval_cleanup_completed: bool = False
    reconciliation_required: bool = False
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True)
class RenameDatasetResult:
    filename_map: dict[str, str]
    filesystem_completed: bool
    approvals_remapped: bool = False
    reconciliation_required: bool = False
    warnings: tuple[str, ...] = ()

    @property
    def count(self) -> int:
        return len(self.filename_map)


@dataclass(frozen=True)
class ExportResult:
    archive_path: Path
    download_name: str


@dataclass(frozen=True)
class ReconciliationReport:
    task_id: str
    stale_filenames: tuple[str, ...]
    removed_filenames: tuple[str, ...] = ()


@dataclass(frozen=True)
class ApprovalMigrationReport:
    task_id: str
    source_path: str
    dry_run: bool
    approvals_discovered: int = 0
    approvals_imported: int = 0
    approvals_would_import: int = 0
    approvals_already_present: int = 0
    approvals_skipped: int = 0
    missing_images: tuple[str, ...] = ()
    malformed_entries: tuple[str, ...] = ()
    migration_failures: tuple[str, ...] = ()

    @property
    def has_errors(self) -> bool:
        return bool(self.missing_images or self.malformed_entries or self.migration_failures)
