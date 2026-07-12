import json
from pathlib import Path

from backend.app.core.config import TaskProfile
from backend.app.repositories.approvals import ApprovalRepository
from backend.app.repositories.dataset import DatasetRepository
from backend.app.services.approval_migration import ApprovalMigrationService
from backend.scripts import migrate_legacy_approvals


def _dataset(tmp_path: Path, task_id: str) -> DatasetRepository:
    image_dir = tmp_path / task_id / "images"
    label_dir = tmp_path / task_id / "labels"
    visualization_dir = tmp_path / task_id / "visualizations"
    for directory in (image_dir, label_dir, visualization_dir):
        directory.mkdir(parents=True)
    return DatasetRepository(image_dir, label_dir, visualization_dir)


def test_migration_imports_valid_legacy_approvals_without_modifying_source(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path, "ppe")
    dataset.image_dir.joinpath("approved.jpg").write_bytes(b"image")
    source = dataset.label_dir / "approved.json"
    source.write_text(json.dumps(["approved.jpg"]), encoding="utf-8")
    approvals = ApprovalRepository(tmp_path / "state.sqlite3")

    report = ApprovalMigrationService("ppe", dataset, approvals).migrate(apply=True)

    assert report.approvals_discovered == 1
    assert report.approvals_imported == 1
    assert approvals.approved_filenames("ppe") == {"approved.jpg"}
    assert json.loads(source.read_text(encoding="utf-8")) == ["approved.jpg"]


def test_dry_run_does_not_modify_sqlite_and_second_apply_is_idempotent(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path, "ppe")
    dataset.image_dir.joinpath("approved.jpg").write_bytes(b"image")
    dataset.label_dir.joinpath("approved.json").write_text('["approved.jpg"]', encoding="utf-8")
    approvals = ApprovalRepository(tmp_path / "state.sqlite3")
    service = ApprovalMigrationService("ppe", dataset, approvals)

    dry_run = service.migrate()
    first_apply = service.migrate(apply=True)
    second_apply = service.migrate(apply=True)

    assert dry_run.approvals_would_import == 1
    assert approvals.approved_filenames("ppe") == {"approved.jpg"}
    assert first_apply.approvals_imported == 1
    assert second_apply.approvals_imported == 0
    assert second_apply.approvals_already_present == 1


def test_migration_reports_missing_and_malformed_entries_while_importing_valid_ones(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path, "ppe")
    dataset.image_dir.joinpath("valid.jpg").write_bytes(b"image")
    dataset.label_dir.joinpath("approved.json").write_text(
        json.dumps(["valid.jpg", "missing.jpg", 123, "../unsafe.jpg", "valid.jpg"]),
        encoding="utf-8",
    )
    approvals = ApprovalRepository(tmp_path / "state.sqlite3")

    report = ApprovalMigrationService("ppe", dataset, approvals).migrate(apply=True)

    assert report.approvals_imported == 1
    assert report.approvals_skipped == 4
    assert report.missing_images == ("missing.jpg",)
    assert len(report.malformed_entries) == 2
    assert report.has_errors is True
    assert approvals.approved_filenames("ppe") == {"valid.jpg"}


def test_migration_reports_malformed_json_as_failure(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path, "ppe")
    dataset.label_dir.joinpath("approved.json").write_text("not json", encoding="utf-8")
    approvals = ApprovalRepository(tmp_path / "state.sqlite3")

    report = ApprovalMigrationService("ppe", dataset, approvals).migrate(apply=True)

    assert report.migration_failures
    assert approvals.approved_filenames("ppe") == set()


def test_cli_migrates_all_configured_tasks(monkeypatch, tmp_path: Path, capsys) -> None:
    ppe_dataset = _dataset(tmp_path, "ppe")
    signs_dataset = _dataset(tmp_path, "safety_signs")
    ppe_dataset.image_dir.joinpath("ppe.jpg").write_bytes(b"image")
    signs_dataset.image_dir.joinpath("sign.jpg").write_bytes(b"image")
    ppe_dataset.label_dir.joinpath("approved.json").write_text('["ppe.jpg"]', encoding="utf-8")
    signs_dataset.label_dir.joinpath("approved.json").write_text('["sign.jpg"]', encoding="utf-8")
    database_path = tmp_path / "state.sqlite3"

    def profile(task_id: str, dataset: DatasetRepository, detector_type: str) -> TaskProfile:
        return TaskProfile(
            id=task_id,
            name=task_id,
            image_dir=dataset.image_dir,
            label_dir=dataset.label_dir,
            visualization_dir=dataset.visualization_dir,
            model_path=tmp_path / f"{task_id}.pt",
            yolo_img_size=640,
            yolo_conf=0.25,
            yolo_iou=0.7,
            class_names={0: "Class"},
            detector_type=detector_type,
        )

    profiles = {
        "ppe": profile("ppe", ppe_dataset, "ppe"),
        "safety_signs": profile("safety_signs", signs_dataset, "safety_signs"),
    }

    class SettingsStub:
        def __init__(self, path: Path) -> None:
            self.database_path = path
            self.task_profiles = profiles

        @staticmethod
        def task_profile(task_id: str) -> TaskProfile:
            return profiles[task_id]

    settings = SettingsStub(database_path)
    monkeypatch.setattr(migrate_legacy_approvals, "get_settings", lambda: settings)

    assert migrate_legacy_approvals.main(["--all", "--apply"]) == 0
    reports = json.loads(capsys.readouterr().out)
    assert {report["task_id"] for report in reports} == {"ppe", "safety_signs"}
    approvals = ApprovalRepository(database_path)
    assert approvals.approved_filenames("ppe") == {"ppe.jpg"}
    assert approvals.approved_filenames("safety_signs") == {"sign.jpg"}
