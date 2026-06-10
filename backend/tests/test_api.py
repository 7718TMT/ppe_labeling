from pathlib import Path

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


def test_put_empty_labels_persists_empty_label_file(monkeypatch, tmp_path: Path) -> None:
    image_dir, label_dir, _, _ = _configure_safety_task(monkeypatch, tmp_path)
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")

    client = TestClient(create_app())
    response = client.put("/api/v1/tasks/safety_signs/images/sample.jpg/labels", json={"boxes": []})

    assert response.status_code == 200
    assert (label_dir / "sample.txt").read_text(encoding="utf-8") == ""
