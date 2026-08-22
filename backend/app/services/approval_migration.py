"""Explicit release-time import of legacy approval JSON into SQLite."""

import json
from pathlib import Path

from backend.app.domain.errors import ApplicationError
from backend.app.domain.models import ApprovalMigrationReport
from backend.app.repositories.approvals import ApprovalRepository
from backend.app.repositories.dataset import DatasetRepository


LEGACY_APPROVAL_FILENAME = "approved.json"


class ApprovalMigrationService:
    """Imports a task's legacy current-state approvals without touching the source file."""

    def __init__(self, task_id: str, dataset: DatasetRepository, approvals: ApprovalRepository) -> None:
        self.task_id = task_id
        self.dataset = dataset
        self.approvals = approvals

    @property
    def source_path(self) -> Path:
        return self.dataset.label_dir / LEGACY_APPROVAL_FILENAME

    def migrate(self, apply: bool = False) -> ApprovalMigrationReport:
        source_path = self.source_path
        if not source_path.exists():
            return ApprovalMigrationReport(task_id=self.task_id, source_path=str(source_path), dry_run=not apply)

        try:
            payload = json.loads(source_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            return ApprovalMigrationReport(
                task_id=self.task_id,
                source_path=str(source_path),
                dry_run=not apply,
                migration_failures=(f"Unable to parse legacy approval JSON: {exc}",),
            )

        if not isinstance(payload, list):
            return ApprovalMigrationReport(
                task_id=self.task_id,
                source_path=str(source_path),
                dry_run=not apply,
                migration_failures=("Legacy approval JSON must contain a list of image filenames.",),
            )

        try:
            existing = self.approvals.approved_filenames(self.task_id)
            image_filenames = self.dataset.image_filenames()
        except Exception as exc:
            return ApprovalMigrationReport(
                task_id=self.task_id,
                source_path=str(source_path),
                dry_run=not apply,
                approvals_discovered=len(payload),
                migration_failures=(f"Unable to inspect migration state: {exc}",),
            )
        seen: set[str] = set()
        imported = 0
        would_import = 0
        already_present = 0
        skipped = 0
        missing_images: list[str] = []
        malformed_entries: list[str] = []
        failures: list[str] = []

        for index, entry in enumerate(payload):
            if not isinstance(entry, str):
                malformed_entries.append(f"Entry {index} is not a filename string.")
                skipped += 1
                continue
            try:
                filename = self.dataset.validate_image_filename(entry)
            except ApplicationError as exc:
                malformed_entries.append(f"Entry {index} ({entry!r}) is invalid: {exc}")
                skipped += 1
                continue
            if filename in seen:
                skipped += 1
                continue
            seen.add(filename)
            if filename not in image_filenames:
                missing_images.append(filename)
                skipped += 1
                continue
            if filename in existing:
                already_present += 1
                continue
            if not apply:
                would_import += 1
                continue
            try:
                self.approvals.set_approval(self.task_id, filename, True)
            except Exception as exc:
                failures.append(f"Unable to import {filename}: {exc}")
                skipped += 1
                continue
            existing.add(filename)
            imported += 1

        return ApprovalMigrationReport(
            task_id=self.task_id,
            source_path=str(source_path),
            dry_run=not apply,
            approvals_discovered=len(payload),
            approvals_imported=imported,
            approvals_would_import=would_import,
            approvals_already_present=already_present,
            approvals_skipped=skipped,
            missing_images=tuple(missing_images),
            malformed_entries=tuple(malformed_entries),
            migration_failures=tuple(failures),
        )
