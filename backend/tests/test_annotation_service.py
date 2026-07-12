import logging
import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_annotation_service
from backend.app.core.config import get_settings
from backend.app.domain.errors import FilesystemOperationError, PartialOperationError
from backend.app.domain.models import DeleteImageResult, RenameDatasetResult
from backend.app.main import create_app
from backend.app.repositories.approvals import ApprovalRepository
from backend.app.repositories.dataset import DatasetRepository
from backend.app.services.annotation import AnnotationService


class FailingApprovalCleanup:
    def delete_approval(self, task_id: str, filename: str) -> None:
        raise sqlite3.OperationalError("database unavailable")


class FailingApprovalRemap:
    def remap_filenames(self, task_id: str, filename_map: dict[str, str]) -> tuple[str, ...]:
        raise sqlite3.OperationalError("database unavailable")


class FailingPostRemapReconciliation:
    def remap_filenames(self, task_id: str, filename_map: dict[str, str]) -> tuple[str, ...]:
        return ()

    def stale_filenames(self, task_id: str, current_filenames: set[str]) -> tuple[str, ...]:
        raise sqlite3.OperationalError("database unavailable")


class FailingFilesystemDelete:
    class ExistingImagePath:
        @staticmethod
        def exists() -> bool:
            return True

    def image_path_for(self, filename: str) -> "FailingFilesystemDelete.ExistingImagePath":
        return self.ExistingImagePath()

    def delete_image_artifacts(self, filename: str) -> DeleteImageResult:
        result = DeleteImageResult(
            filename=filename,
            filesystem_completed=False,
            reconciliation_required=True,
            warnings=("Filesystem deletion did not complete; inspect the dataset artifacts before retrying.",),
        )
        raise FilesystemOperationError("Filesystem deletion did not complete", result)


class FailingFilesystemRename:
    def rename_dataset_sequential(self) -> RenameDatasetResult:
        result = RenameDatasetResult(
            filename_map={"source.jpg": "image_00000.jpg"},
            filesystem_completed=False,
            reconciliation_required=True,
            warnings=("Filesystem rename did not complete; inspect .renaming artifacts before retrying.",),
        )
        raise FilesystemOperationError("Filesystem rename did not complete", result)


def _dataset(tmp_path: Path) -> DatasetRepository:
    image_dir = tmp_path / "images"
    label_dir = tmp_path / "labels"
    visualization_dir = tmp_path / "visualizations"
    image_dir.mkdir()
    label_dir.mkdir()
    visualization_dir.mkdir()
    return DatasetRepository(image_dir, label_dir, visualization_dir)


def _service(dataset: DatasetRepository, approvals: object) -> AnnotationService:
    return AnnotationService("ppe", dataset, approvals, None, {0: "Person"})  # type: ignore[arg-type]


def test_delete_reports_partial_result_when_approval_cleanup_fails(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    dataset = _dataset(tmp_path)
    dataset.image_dir.joinpath("sample.jpg").write_bytes(b"image")
    dataset.label_dir.joinpath("sample.txt").write_text("", encoding="utf-8")

    with caplog.at_level(logging.ERROR), pytest.raises(PartialOperationError) as error:
        _service(dataset, FailingApprovalCleanup()).delete_image("sample.jpg")

    result = error.value.result
    assert isinstance(result, DeleteImageResult)
    assert result.filesystem_completed is True
    assert result.approval_cleanup_completed is False
    assert result.reconciliation_required is True
    assert not dataset.image_dir.joinpath("sample.jpg").exists()
    assert "Approval cleanup failed after image deletion" in caplog.text


def test_rename_reports_partial_result_when_approval_remap_fails(tmp_path: Path, caplog: pytest.LogCaptureFixture) -> None:
    dataset = _dataset(tmp_path)
    dataset.image_dir.joinpath("source.jpg").write_bytes(b"image")

    with caplog.at_level(logging.ERROR), pytest.raises(PartialOperationError) as error:
        _service(dataset, FailingApprovalRemap()).rename_dataset_sequential()

    result = error.value.result
    assert isinstance(result, RenameDatasetResult)
    assert result.filesystem_completed is True
    assert result.approvals_remapped is False
    assert result.reconciliation_required is True
    assert dataset.image_dir.joinpath("image_00000.jpg").exists()
    assert "Approval remapping failed after dataset rename" in caplog.text


def test_rename_reports_completed_remap_when_post_remap_reconciliation_fails(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    dataset = _dataset(tmp_path)
    dataset.image_dir.joinpath("source.jpg").write_bytes(b"image")

    with caplog.at_level(logging.ERROR), pytest.raises(PartialOperationError) as error:
        _service(dataset, FailingPostRemapReconciliation()).rename_dataset_sequential()

    result = error.value.result
    assert isinstance(result, RenameDatasetResult)
    assert result.filesystem_completed is True
    assert result.approvals_remapped is True
    assert result.reconciliation_required is True
    assert dataset.image_dir.joinpath("image_00000.jpg").exists()
    assert "Stale approval cleanup failed after dataset rename" in caplog.text


@pytest.mark.parametrize(
    ("dataset", "operation"),
    [
        (FailingFilesystemDelete(), lambda service: service.delete_image("sample.jpg")),
        (FailingFilesystemRename(), lambda service: service.rename_dataset_sequential()),
    ],
)
def test_filesystem_failures_are_exposed_as_partial_operations(dataset: object, operation) -> None:
    with pytest.raises(PartialOperationError) as error:
        operation(_service(dataset, object()))  # type: ignore[arg-type]

    assert error.value.result.filesystem_completed is False
    assert error.value.result.reconciliation_required is True


def test_rename_removes_stale_target_approval_before_remapping(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    dataset.image_dir.joinpath("source.jpg").write_bytes(b"image")
    approvals = ApprovalRepository(tmp_path / "state.sqlite3")
    approvals.set_approval("ppe", "source.jpg", True)
    approvals.set_approval("ppe", "image_00000.jpg", True)

    result = _service(dataset, approvals).rename_dataset_sequential()

    assert result.filesystem_completed is True
    assert result.approvals_remapped is True
    assert result.warnings == ("Removed stale approval metadata: image_00000.jpg",)
    assert approvals.approved_filenames("ppe") == {"image_00000.jpg"}


def test_reconciliation_reports_and_safely_repeats_stale_approval_cleanup(tmp_path: Path) -> None:
    dataset = _dataset(tmp_path)
    dataset.image_dir.joinpath("present.jpg").write_bytes(b"image")
    approvals = ApprovalRepository(tmp_path / "state.sqlite3")
    approvals.set_approval("ppe", "missing.jpg", True)
    approvals.set_approval("ppe", "present.jpg", True)
    service = _service(dataset, approvals)

    assert service.reconcile_approvals().stale_filenames == ("missing.jpg",)
    assert service.reconcile_approvals(remove=True).removed_filenames == ("missing.jpg",)
    assert service.reconcile_approvals(remove=True).stale_filenames == ()
    assert approvals.approved_filenames("ppe") == {"present.jpg"}


def test_partial_operation_api_response_exposes_operation_state(monkeypatch, tmp_path: Path) -> None:
    class PartialDeleteService:
        def delete_image(self, filename: str) -> None:
            result = DeleteImageResult(
                filename=filename,
                filesystem_completed=True,
                reconciliation_required=True,
                warnings=("Approval cleanup failed.",),
            )
            raise PartialOperationError("Image deleted but approval reconciliation is required", result)

    monkeypatch.setenv("DATABASE_PATH", str(tmp_path / "state.sqlite3"))
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_annotation_service] = PartialDeleteService

    response = TestClient(app).delete("/api/v1/tasks/ppe/images/sample.jpg")

    assert response.status_code == 500
    assert response.json() == {
        "detail": "Image deleted but approval reconciliation is required",
        "reconciliation_required": True,
        "operation": {
            "filename": "sample.jpg",
            "filesystem_completed": True,
            "approval_cleanup_completed": False,
            "reconciliation_required": True,
            "warnings": ["Approval cleanup failed."],
        },
    }
