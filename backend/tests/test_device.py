from types import SimpleNamespace
import sys

from backend.app.core.device import resolve_inference_device


class _FakeCuda:
    def __init__(self, available: bool, count: int = 1) -> None:
        self._available = available
        self._count = count

    def is_available(self) -> bool:
        return self._available

    def device_count(self) -> int:
        return self._count


def test_auto_device_uses_cuda_when_available(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=_FakeCuda(available=True, count=2)))

    assert resolve_inference_device("auto") == "cuda:0"


def test_explicit_cuda_index_is_validated(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=_FakeCuda(available=True, count=2)))

    assert resolve_inference_device("1") == "cuda:1"
    assert resolve_inference_device("cuda:3") == "cpu"


def test_cuda_request_falls_back_to_cpu_when_unavailable(monkeypatch) -> None:
    monkeypatch.setitem(sys.modules, "torch", SimpleNamespace(cuda=_FakeCuda(available=False, count=0)))

    assert resolve_inference_device("cuda") == "cpu"
