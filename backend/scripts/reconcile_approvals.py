"""Inspect or remove approval rows for images that no longer exist on disk.

Run from the repository root:
    uv run python -m backend.scripts.reconcile_approvals --task ppe
    uv run python -m backend.scripts.reconcile_approvals --task ppe --apply
"""

import argparse
import json
from dataclasses import asdict
from typing import Sequence

from backend.app.core.config import get_settings
from backend.app.domain.errors import UnknownTaskError
from backend.app.repositories.approvals import ApprovalRepository
from backend.app.repositories.dataset import DatasetRepository
from backend.app.services.reconciliation import ApprovalReconciliationService


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Reconcile stale SQLite approval metadata with filesystem images.")
    parser.add_argument("--task", required=True, help="Configured task identifier, for example ppe or safety_signs.")
    parser.add_argument("--apply", action="store_true", help="Delete stale approval rows after reporting them.")
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    settings = get_settings()
    try:
        profile = settings.task_profile(args.task)
    except UnknownTaskError as exc:
        raise SystemExit(str(exc)) from exc

    dataset = DatasetRepository(profile.image_dir, profile.label_dir, profile.visualization_dir)
    approvals = ApprovalRepository(settings.database_path)
    report = ApprovalReconciliationService(profile.id, dataset, approvals).run(remove=args.apply)
    print(json.dumps(asdict(report), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
