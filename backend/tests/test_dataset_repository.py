from pathlib import Path

import pytest

from backend.app.domain.errors import DatasetCollisionError, FilesystemOperationError, InvalidFilenameError, InvalidLabelError
from backend.app.domain.models import BoundingBox
from backend.app.repositories.dataset import DatasetRepository


@pytest.fixture
def dataset(tmp_path: Path) -> DatasetRepository:
    image_dir = tmp_path / "images"
    label_dir = tmp_path / "labels"
    visualization_dir = tmp_path / "visualizations"
    image_dir.mkdir()
    label_dir.mkdir()
    visualization_dir.mkdir()
    return DatasetRepository(image_dir, label_dir, visualization_dir)


def test_labels_round_trip_through_dataset_repository(dataset: DatasetRepository) -> None:
    box = BoundingBox(class_id=3, x_center=0.5, y_center=0.4, w=0.2, h=0.1)

    dataset.save_labels("sample.jpg", [box])

    assert dataset.read_labels("sample.jpg") == [box]


def test_dataset_repository_rejects_invalid_filenames(dataset: DatasetRepository) -> None:
    with pytest.raises(InvalidFilenameError):
        dataset.read_labels("../sample.jpg")

    with pytest.raises(InvalidFilenameError):
        dataset.read_labels("nested/sample.jpg")


def test_dataset_repository_rejects_invalid_label_rows(dataset: DatasetRepository) -> None:
    dataset.label_dir.joinpath("sample.txt").write_text("0 0.5 0.5\n", encoding="utf-8")

    with pytest.raises(InvalidLabelError):
        dataset.read_labels("sample.jpg")


def test_dataset_repository_writes_empty_label_files(dataset: DatasetRepository) -> None:
    dataset.save_labels("sample.jpg", [])

    assert dataset.label_path_for("sample.jpg").read_text(encoding="utf-8") == ""


def test_sequential_rename_rejects_unexpected_target_collisions(dataset: DatasetRepository) -> None:
    dataset.image_dir.joinpath("source.jpg").write_bytes(b"source")
    dataset.label_dir.joinpath("image_00000.txt").write_text("orphan", encoding="utf-8")

    with pytest.raises(DatasetCollisionError):
        dataset.rename_dataset_sequential()

    assert dataset.image_dir.joinpath("source.jpg").exists()


def test_delete_reports_filesystem_partial_failure(dataset: DatasetRepository, monkeypatch: pytest.MonkeyPatch) -> None:
    image_path = dataset.image_dir / "sample.jpg"
    image_path.write_bytes(b"image")
    original_unlink = Path.unlink

    def fail_image_unlink(path: Path, *args, **kwargs) -> None:
        if path == image_path:
            raise OSError("disk error")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_image_unlink)

    with pytest.raises(FilesystemOperationError) as error:
        dataset.delete_image_artifacts("sample.jpg")

    assert error.value.result.filesystem_completed is False
    assert error.value.result.reconciliation_required is True
    assert image_path.exists()


def test_rename_reports_filesystem_partial_failure(dataset: DatasetRepository, monkeypatch: pytest.MonkeyPatch) -> None:
    source_path = dataset.image_dir / "source.jpg"
    source_path.write_bytes(b"image")
    original_rename = Path.rename

    def fail_final_image_rename(path: Path, target: Path):
        if path.name.endswith(".renaming"):
            raise OSError("disk error")
        return original_rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_final_image_rename)

    with pytest.raises(FilesystemOperationError) as error:
        dataset.rename_dataset_sequential()

    assert error.value.result.filesystem_completed is False
    assert error.value.result.reconciliation_required is True
    assert dataset.image_dir.joinpath("source.jpg.renaming").exists()


def test_sequential_rename_rejects_unfinished_temporary_artifacts(dataset: DatasetRepository) -> None:
    dataset.image_dir.joinpath("source.jpg").write_bytes(b"image")
    temporary_path = dataset.image_dir / "previous.jpg.renaming"
    temporary_path.write_bytes(b"incomplete")

    with pytest.raises(DatasetCollisionError, match="Unfinished sequential rename artifacts"):
        dataset.rename_dataset_sequential()

    assert dataset.image_dir.joinpath("source.jpg").exists()
    assert temporary_path.exists()


def test_uploaded_images_get_unique_stems_across_extensions(dataset: DatasetRepository) -> None:
    dataset.image_dir.joinpath("same.jpg").write_bytes(b"image")

    stored_name = dataset.save_uploaded_image("same.png", b"image")

    assert stored_name == "same_001.png"
    assert dataset.image_dir.joinpath("same_001.png").exists()


def test_dataset_artifact_operations_reject_duplicate_image_stems(dataset: DatasetRepository) -> None:
    dataset.image_dir.joinpath("same.jpg").write_bytes(b"jpg")
    dataset.image_dir.joinpath("same.png").write_bytes(b"png")

    with pytest.raises(DatasetCollisionError, match="label and visualization stem"):
        dataset.save_labels("same.jpg", [])
    with pytest.raises(DatasetCollisionError, match="label and visualization stem"):
        dataset.delete_image_artifacts("same.jpg")
    with pytest.raises(DatasetCollisionError, match="label and visualization stem"):
        dataset.rename_dataset_sequential()

    assert dataset.image_dir.joinpath("same.jpg").exists()
    assert dataset.image_dir.joinpath("same.png").exists()
