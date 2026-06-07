from pathlib import Path

import pytest
from fastapi import HTTPException

from backend.app.models.schemas import BoundingBox
from backend.app.services import storage


def test_validate_image_filename_rejects_path_traversal() -> None:
    with pytest.raises(HTTPException):
        storage.validate_image_filename("../image.jpg")

    with pytest.raises(HTTPException):
        storage.validate_image_filename("nested/image.jpg")


def test_save_labels_writes_empty_file(tmp_path: Path) -> None:
    storage.save_labels(tmp_path, "sample.jpg", [])

    label_path = tmp_path / "sample.txt"
    assert label_path.exists()
    assert label_path.read_text(encoding="utf-8") == ""


def test_read_labels_rejects_malformed_rows(tmp_path: Path) -> None:
    (tmp_path / "sample.txt").write_text("0 0.5 0.5\n", encoding="utf-8")

    with pytest.raises(HTTPException):
        storage.read_labels(tmp_path, "sample.jpg")


def test_save_and_read_labels_round_trip(tmp_path: Path) -> None:
    box = BoundingBox(class_id=1, x_center=0.5, y_center=0.4, w=0.2, h=0.1)

    storage.save_labels(tmp_path, "sample.jpg", [box])

    assert storage.read_labels(tmp_path, "sample.jpg") == [box]
