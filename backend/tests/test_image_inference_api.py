from pathlib import Path

import cv2
import numpy as np
from fastapi.testclient import TestClient

from backend.app.api.dependencies.image import get_detector
from backend.app.core.config import get_settings
from backend.app.domain.models import BoundingBox
from backend.app.main import create_app


class FakeDetector:
    def detect_image(self, image) -> list[BoundingBox]:
        assert image.shape[:2] == (24, 32)
        return [BoundingBox(class_id=0, x_center=0.5, y_center=0.5, w=0.5, h=0.5)]


def test_image_inference_upload_list_media_and_delete(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IMAGE_INFERENCE_STORAGE_ROOT", str(tmp_path / "inference"))
    get_settings.cache_clear()
    app = create_app()
    app.dependency_overrides[get_detector] = lambda: FakeDetector()
    client = TestClient(app)
    ok, encoded = cv2.imencode(".jpg", np.zeros((24, 32, 3), dtype=np.uint8))
    assert ok

    upload = client.post(
        "/api/v1/tasks/ppe/inference",
        files=[("files", ("worker.jpg", encoded.tobytes(), "image/jpeg"))],
    )
    assert upload.status_code == 200
    item = upload.json()[0]
    assert item["media_type"] == "image"
    assert item["detections"] == 1
    assert item["result_url"].endswith(f'/{item["id"]}/result')

    listing = client.get("/api/v1/tasks/ppe/inference")
    assert listing.status_code == 200
    assert listing.json() == [item]
    result = client.get(item["result_url"])
    assert result.status_code == 200
    assert result.headers["content-type"].startswith("image/jpeg")

    deleted = client.delete(f'/api/v1/tasks/ppe/inference/{item["id"]}')
    assert deleted.status_code == 200
    assert client.get("/api/v1/tasks/ppe/inference").json() == []


def test_video_inference_returns_browser_compatible_mp4(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("IMAGE_INFERENCE_STORAGE_ROOT", str(tmp_path / "inference"))
    get_settings.cache_clear()
    source = tmp_path / "sample.mp4"
    writer = cv2.VideoWriter(str(source), cv2.VideoWriter_fourcc(*"mp4v"), 4.0, (32, 24))
    assert writer.isOpened()
    for _ in range(3):
        writer.write(np.zeros((24, 32, 3), dtype=np.uint8))
    writer.release()

    app = create_app()
    app.dependency_overrides[get_detector] = lambda: FakeDetector()
    client = TestClient(app)
    upload = client.post(
        "/api/v1/tasks/ppe/inference",
        files=[("files", ("factory.mp4", source.read_bytes(), "video/mp4"))],
    )

    assert upload.status_code == 200
    item = upload.json()[0]
    assert item["media_type"] == "video"
    assert item["detections"] == 3
    result = client.get(item["result_url"])
    assert result.status_code == 200
    assert result.headers["content-type"].startswith("video/mp4")
    assert b"avc1" in result.content[:128]
