import logging


logger = logging.getLogger(__name__)


def resolve_inference_device(requested_device: str = "auto") -> str:
    requested = requested_device.strip().lower()
    if not requested or requested == "auto":
        return "cuda:0" if _cuda_available() else "cpu"

    if requested == "cpu":
        return "cpu"

    if requested.isdigit():
        requested = f"cuda:{requested}"
    elif requested == "cuda":
        requested = "cuda:0"

    if requested.startswith("cuda"):
        if not _cuda_available():
            logger.warning(
                "Requested %s, but PyTorch cannot access CUDA. Falling back to CPU.",
                requested_device,
                extra={"requested_device": requested_device, "resolved_device": "cpu"},
            )
            return "cpu"

        index = _cuda_device_index(requested)
        if index is None:
            logger.warning(
                "Invalid CUDA device value %s. Falling back to CPU.",
                requested_device,
                extra={"requested_device": requested_device, "resolved_device": "cpu"},
            )
            return "cpu"

        device_count = _cuda_device_count()
        if index >= device_count:
            logger.warning(
                "Requested CUDA device %s, but only %s CUDA device(s) are available. Falling back to CPU.",
                requested_device,
                device_count,
                extra={"requested_device": requested_device, "resolved_device": "cpu"},
            )
            return "cpu"

        return f"cuda:{index}"

    logger.warning(
        "Unknown inference device %s. Falling back to CPU.",
        requested_device,
        extra={"requested_device": requested_device, "resolved_device": "cpu"},
    )
    return "cpu"


def _cuda_available() -> bool:
    try:
        import torch

        return bool(torch.cuda.is_available())
    except Exception:
        return False


def _cuda_device_count() -> int:
    try:
        import torch

        return int(torch.cuda.device_count())
    except Exception:
        return 0


def _cuda_device_index(device: str) -> int | None:
    if device == "cuda":
        return 0
    if not device.startswith("cuda:"):
        return None
    value = device.split(":", 1)[1]
    if not value.isdigit():
        return None
    return int(value)
