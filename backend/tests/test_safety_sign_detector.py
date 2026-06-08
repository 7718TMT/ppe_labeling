from pathlib import Path
from types import SimpleNamespace
import sys

import numpy as np

from backend.app.ml.safety_sign_detector import SafetySignDetector


class _FakeTensor:
    def __init__(self, values):
        self._values = values

    def tolist(self):
        return self._values


class _FakeBoxes:
    xywhn = _FakeTensor([[0.5, 0.5, 0.2, 0.3], [0.25, 0.25, 0.1, 0.1], [0.75, 0.75, 0.1, 0.1]])
    cls = _FakeTensor([0, 3, 7])


class _FakeResult:
    boxes = _FakeBoxes()


class _FakeModel:
    def __init__(self) -> None:
        self.called = False

    def __call__(self, image_path: Path, imgsz: int, conf: float, iou: float, agnostic_nms: bool, verbose: bool):
        assert imgsz == 640
        assert conf == 0.15
        assert iou == 0.7
        assert agnostic_nms is False
        assert verbose is False
        self.called = True
        return [_FakeResult()]


def test_safety_sign_detector_preserves_trained_model_classes(monkeypatch, tmp_path: Path) -> None:
    image_path = tmp_path / "sample.jpg"
    image_path.write_bytes(b"placeholder")
    fake_model = _FakeModel()

    monkeypatch.setattr("cv2.imread", lambda _: np.zeros((100, 100, 3), dtype=np.uint8))

    detector = SafetySignDetector(
        model_path=tmp_path / "sign.pt",
        allowed_class_ids={0, 1, 2, 3},
    )
    detector._model = fake_model

    boxes = detector.detect(image_path)

    assert [box.class_id for box in boxes] == [0, 3]
    assert fake_model.called is True


def test_safety_sign_detector_loads_regular_yolo_model_without_prompts(monkeypatch, tmp_path: Path) -> None:
    model_path = tmp_path / "sign.pt"
    model_path.write_bytes(b"placeholder")
    fake_model = _FakeModel()

    monkeypatch.setitem(sys.modules, "ultralytics", SimpleNamespace(YOLO=lambda _: fake_model))

    detector = SafetySignDetector(
        model_path=model_path,
        allowed_class_ids={0, 1, 2, 3},
    )

    assert detector.model is fake_model
