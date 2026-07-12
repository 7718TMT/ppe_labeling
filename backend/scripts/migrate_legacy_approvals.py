"""Import base-branch ``approved.json`` state into SQLite as an explicit release action.

Examples:
    uv run python -m backend.scripts.migrate_legacy_approvals --task ppe
    uv run python -m backend.scripts.migrate_legacy_approvals --all --apply
"""

import argparse
import json
from dataclasses import asdict
from typing import Sequence

from backend.app.core.config import Settings, get_settings
from backend.app.domain.errors import UnknownTaskError
from backend.app.domain.models import ApprovalMigrationReport
from backend.app.repositories.approvals import ApprovalRepository
from backend.app.repositories.dataset import DatasetRepository
from backend.app.services.approval_migration import ApprovalMigrationService


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate legacy labels/approved.json approval state into SQLite.")
    scope = parser.add_mutually_exclusive_group(required=True)
    scope.add_argument("--task", help="Configured task identifier, for example ppe or safety_signs.")
    scope.add_argument("--all", action="store_true", help="Migrate every configured task.")
    parser.add_argument("--apply", action="store_true", help="Write missing approvals to SQLite. The default is dry-run.")
    return parser.parse_args(argv)


def migrate_profiles(settings: Settings, task_ids: Sequence[str], apply: bool) -> list[ApprovalMigrationReport]:
    reports: list[ApprovalMigrationReport] = []
    for task_id in task_ids:
        profile = settings.task_profile(task_id)
        dataset = DatasetRepository(profile.image_dir, profile.label_dir, profile.visualization_dir)
        try:
            approvals = ApprovalRepository(settings.database_path)
        except Exception as exc:
            reports.append(
                ApprovalMigrationReport(
                    task_id=profile.id,
                    source_path=str(dataset.label_dir / "approved.json"),
                    dry_run=not apply,
                    migration_failures=(f"Unable to initialize approval repository: {exc}",),
                )
            )
            continue
        reports.append(ApprovalMigrationService(profile.id, dataset, approvals).migrate(apply=apply))
    return reports


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    if args.all:
        task_ids = list(settings.task_profiles)
    else:
        task_ids = [args.task]
    try:
        reports = migrate_profiles(settings, task_ids, apply=args.apply)
    except UnknownTaskError as exc:
        raise SystemExit(str(exc)) from exc

    print(json.dumps([asdict(report) for report in reports], indent=2))
    return 1 if any(report.has_errors for report in reports) else 0


if __name__ == "__main__":
    raise SystemExit(main())
