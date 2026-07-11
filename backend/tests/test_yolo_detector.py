from pathlib import Path

import numpy as np
import pytest

from backend.app.ml.yolo_detector import PpeDetector


class _FakeTensor:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values


class _FakeBoxes:
    xywhn = _FakeTensor(
        [
            [0.5, 0.5, 0.8, 0.9],
            [0.5, 0.12, 0.2, 0.1],
            [0.5, 0.55, 0.35, 0.3],
            [0.25, 0.55, 0.2, 0.4],
            [0.75, 0.55, 0.2, 0.4],
        ]
    )
    cls = _FakeTensor([0, 1, 2, 3, 8])


class _FakeResult:
    boxes = _FakeBoxes()


class _FakeModel:
    def __call__(self, image_path: Path, imgsz: int, conf: float, iou: float, device: str, verbose: bool):
        assert imgsz == 960
        assert conf == 0.4
        assert iou == 0.6
        assert device == "cpu"
        assert verbose is False
        return [_FakeResult()]


def test_detector_uses_yolo_vest_boxes_directly(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "sample.jpg"
    image_path.write_bytes(b"placeholder")

    monkeypatch.setattr("cv2.imread", lambda _: np.zeros((100, 100, 3), dtype=np.uint8))

    detector = PpeDetector(
        model_path=tmp_path / "model.pt",
        image_size=960,
        confidence=0.4,
        iou=0.6,
        allowed_class_ids={0, 1, 2, 3},
        use_color_vest_fallback=False,
        device="cpu",
    )
    detector._model = _FakeModel()

    boxes = detector.detect(image_path)

    assert [box.class_id for box in boxes] == [0, 1, 2, 3]
    assert boxes[2].x_center == pytest.approx(0.5)
    assert boxes[2].y_center == pytest.approx(0.55)
    assert boxes[2].w == pytest.approx(0.35)
    assert boxes[2].h == pytest.approx(0.3)
    assert boxes[3].class_id == 3
