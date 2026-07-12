import json
from pathlib import Path

from backend.app.core.config import TaskProfile
from backend.app.repositories.approvals import ApprovalRepository
from backend.scripts import reconcile_approvals


def test_reconciliation_command_reports_then_removes_stale_approvals(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    image_dir = tmp_path / "images"
    label_dir = tmp_path / "labels"
    visualization_dir = tmp_path / "visualizations"
    for directory in (image_dir, label_dir, visualization_dir):
        directory.mkdir()
    image_dir.joinpath("present.jpg").write_bytes(b"image")

    profile = TaskProfile(
        id="ppe",
        name="PPE",
        image_dir=image_dir,
        label_dir=label_dir,
        visualization_dir=visualization_dir,
        model_path=tmp_path / "weights.pt",
        yolo_img_size=640,
        yolo_conf=0.25,
        yolo_iou=0.7,
        class_names={0: "Person"},
        detector_type="ppe",
    )
    database_path = tmp_path / "state.sqlite3"
    approvals = ApprovalRepository(database_path)
    approvals.set_approval("ppe", "missing.jpg", True)

    class SettingsStub:
        def __init__(self, path: Path) -> None:
            self.database_path = path

        @staticmethod
        def task_profile(task_id: str) -> TaskProfile:
            assert task_id == "ppe"
            return profile

    settings = SettingsStub(database_path)
    monkeypatch.setattr(reconcile_approvals, "get_settings", lambda: settings)

    assert reconcile_approvals.main(["--task", "ppe"]) == 0
    assert json.loads(capsys.readouterr().out)["stale_filenames"] == ["missing.jpg"]

    assert reconcile_approvals.main(["--task", "ppe", "--apply"]) == 0
    assert json.loads(capsys.readouterr().out)["removed_filenames"] == ["missing.jpg"]
    assert approvals.approved_filenames("ppe") == set()
