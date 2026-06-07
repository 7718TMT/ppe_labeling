from pathlib import Path

from fastapi.testclient import TestClient

from backend.app.core.config import get_settings
from backend.app.main import create_app


def test_image_list_uses_v1_api_and_media_urls(monkeypatch, tmp_path: Path) -> None:
    image_dir = tmp_path / "images"
    label_dir = tmp_path / "labels"
    visualization_dir = tmp_path / "visualizations"
    model_path = tmp_path / "models" / "best.pt"

    monkeypatch.setenv("IMAGE_DIR", str(image_dir))
    monkeypatch.setenv("LABEL_DIR", str(label_dir))
    monkeypatch.setenv("VISUALIZATION_DIR", str(visualization_dir))
    monkeypatch.setenv("MODEL_PATH", str(model_path))
    get_settings.cache_clear()

    image_dir.mkdir(parents=True)
    label_dir.mkdir(parents=True)
    visualization_dir.mkdir(parents=True)
    model_path.parent.mkdir(parents=True)
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")
    (label_dir / "sample.txt").write_text("", encoding="utf-8")

    client = TestClient(create_app())
    response = client.get("/api/v1/images")

    assert response.status_code == 200
    assert response.json() == [
        {
            "name": "sample.jpg",
            "has_label": True,
            "image_url": "/media/images/sample.jpg",
            "visualization_url": None,
        }
    ]


def test_put_empty_labels_persists_empty_label_file(monkeypatch, tmp_path: Path) -> None:
    image_dir = tmp_path / "images"
    label_dir = tmp_path / "labels"
    visualization_dir = tmp_path / "visualizations"
    model_path = tmp_path / "models" / "best.pt"

    monkeypatch.setenv("IMAGE_DIR", str(image_dir))
    monkeypatch.setenv("LABEL_DIR", str(label_dir))
    monkeypatch.setenv("VISUALIZATION_DIR", str(visualization_dir))
    monkeypatch.setenv("MODEL_PATH", str(model_path))
    get_settings.cache_clear()

    image_dir.mkdir(parents=True)
    label_dir.mkdir(parents=True)
    visualization_dir.mkdir(parents=True)
    model_path.parent.mkdir(parents=True)
    (image_dir / "sample.jpg").write_bytes(b"not-real-image")

    client = TestClient(create_app())
    response = client.put("/api/v1/images/sample.jpg/labels", json={"boxes": []})

    assert response.status_code == 200
    assert (label_dir / "sample.txt").read_text(encoding="utf-8") == ""
