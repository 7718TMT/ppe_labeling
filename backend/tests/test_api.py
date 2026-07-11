from pathlib import Path
from io import BytesIO
from zipfile import ZipFile

from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.main import create_app


def _configure_safety_task(monkeypatch, tmp_path: Path) -> tuple[Path, Path, Path, Path]:
    image_dir = tmp_path / "safety_signs" / "images"
    label_dir = tmp_path / "safety_signs" / "labels"
    visualization_dir = tmp_path / "safety_signs" / "visualizations"
    model_path = tmp_path / "weights" / "sign.pt"

    monkeypatch.setenv("ACTIVE_TASK", "safety_signs")
    monkeypatch.setenv("SAFETY_SIGN_IMAGE_DIR", str(image_dir))
    monkeypatch.setenv("SAFETY_SIGN_LABEL_DIR", str(label_dir))
    monkeypatch.setenv("SAFETY_SIGN_VISUALIZATION_DIR", str(visualization_dir))
    monkeypatch.setenv("SAFETY_SIGN_MODEL_PATH", str(model_path))
    get_settings.cache_clear()

    image_dir.mkdir(parents=True)
    label_dir.mkdir(parents=True)
    visualization_dir.mkdir(parents=True)
    model_path.parent.mkdir(parents=True)
    return image_dir, label_dir, visualization_dir, model_path


def test_tasks_endpoint_lists_safety_sign_profile(monkeypatch, tmp_path: Path) -> None:
    _configure_safety_task(monkeypatch, tmp_path)

    client = TestClient(create_app())
    response = client.get("/api/v1/tasks")

    assert response.status_code == 200
    tasks = response.json()
    safety_task = next(task for task in tasks if task["id"] == "safety_signs")
    assert safety_task["temporary_class_id"] is None
    assert safety_task["class_names"]["0"].startswith("M014")
    assert safety_task["class_names"]["3"].startswith("W011")
    assert "4" not in safety_task["class_names"]
    ppe_task = next(task for task in tasks if task["id"] == "ppe")
    assert ppe_task["class_names"]["3"] == "Cleaning Coverall"


def test_task_image_list_uses_scoped_media_urls(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")
    (label_dir / "sample.txt").write_text("", encoding="utf-8")

    client = TestClient(create_app())
    response = client.get("/api/v1/tasks/safety_signs/images")

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "sample.jpg",
            "has_label": True,
            "image_url": "/media/safety_signs/images/sample.jpg",
            "visualization_url": None,
        }
    ]


def test_upload_images_adds_files_to_task(monkeypatch, tmp_path: Path) -> None:
    image_dir, _, _, _ = _configure_safety_task(monkeypatch, tmp_path)

    client = TestClient(create_app())
    response = client.post(
        "/api/v1/tasks/safety_signs/images/upload",
        files=[
            ("files", ("sample.jpg", b"image-one", "image/jpeg")),
            ("files", ("sample.jpg", b"image-two", "image/jpeg")),
        ],
    )

    assert response.status_code == 200
    assert sorted(path.name for path in image_dir.iterdir()) == ["sample.jpg", "sample_001.jpg"]


def test_export_current_image_includes_image_and_empty_label(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "sample.jpg").write_bytes(b"image")

    client = TestClient(create_app())
    response = client.get("/api/v1/tasks/safety_signs/images/sample.jpg/export")

    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == ["images/sample.jpg", "labels/sample.txt"]
        assert archive.read("labels/sample.txt") == b""
    assert (label_dir / "sample.txt").exists()


def test_export_all_includes_all_image_label_pairs(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "a.jpg").write_bytes(b"a")
    (image_dir / "b.png").write_bytes(b"b")
    (label_dir / "a.txt").write_text("0 0.500000 0.500000 0.200000 0.200000\n", encoding="utf-8")

    client = TestClient(create_app())
    response = client.get("/api/v1/tasks/safety_signs/export")

    assert response.status_code == 200
    with ZipFile(BytesIO(response.content)) as archive:
        assert sorted(archive.namelist()) == ["images/a.jpg", "images/b.png", "labels/a.txt", "labels/b.txt"]


def test_rename_sequential_keeps_images_and_labels_together(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, visualization_dir, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "z.png").write_bytes(b"z")
    (image_dir / "a.jpg").write_bytes(b"a")
    (label_dir / "z.txt").write_text("3 0.500000 0.500000 0.200000 0.200000\n", encoding="utf-8")
    (visualization_dir / "verified_z.jpg").write_bytes(b"visual")

    client = TestClient(create_app())
    response = client.post("/api/v1/tasks/safety_signs/rename-sequential")

    assert response.status_code == 200
    assert sorted(path.name for path in image_dir.iterdir()) == ["image_00000.jpg", "image_00001.png"]
    assert (label_dir / "image_00000.txt").read_text(encoding="utf-8") == ""
    assert (label_dir / "image_00001.txt").read_text(encoding="utf-8").startswith("3 ")
    assert (visualization_dir / "verified_image_00001.jpg").exists()


def test_put_empty_labels_persists_empty_label_file(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")

    client = TestClient(create_app())
    response = client.put("/api/v1/tasks/safety_signs/images/sample.jpg/labels", json={"boxes": []})

    assert response.status_code == 200
    assert (label_dir / "sample.txt").read_text(encoding="utf-8") == ""


def test_put_labels_rejects_classes_outside_task_map(monkeypatch, tmp_path: Path) -> None:
    image_dir, _, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")

    client = TestClient(create_app())
    response = client.put(
        "/api/v1/tasks/safety_signs/images/sample.jpg/labels",
        json={"boxes": [{"class_id": 8, "x_center": 0.5, "y_center": 0.5, "w": 0.2, "h": 0.2}]},
    )

    assert response.status_code == 422
    assert "Allowed class IDs: 0, 1, 2, 3" in response.json()["detail"]


def test_custom_task_class_map_accepts_added_class(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    monkeypatch.setenv("SAFETY_SIGN_CLASS_NAMES", "0=Base Sign|8=Extra Sign")
    get_settings.cache_clear()
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")

    client = TestClient(create_app())
    response = client.put(
        "/api/v1/tasks/safety_signs/images/sample.jpg/labels",
        json={"boxes": [{"class_id": 8, "x_center": 0.5, "y_center": 0.5, "w": 0.2, "h": 0.2}]},
    )

    assert response.status_code == 200
    assert (label_dir / "sample.txt").read_text(encoding="utf-8").startswith("8 ")
