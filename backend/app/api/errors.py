from dataclasses import asdict, is_dataclass

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from backend.app.domain.errors import (
    ApplicationError,
    ApprovalPersistenceError,
    DatasetCollisionError,
    ImageNotFoundError,
    InvalidClassError,
    InvalidFilenameError,
    InvalidLabelError,
    ModelUnavailableError,
    PartialOperationError,
    UnknownTaskError,
    UnreadableImageError,
    UnsupportedImageTypeError,
)


def register_exception_handlers(app: FastAPI) -> None:
    """Map framework-independent application errors to stable HTTP responses."""

    @app.exception_handler(ApplicationError)
    async def application_error_handler(_: Request, exc: ApplicationError) -> JSONResponse:
        status_code = _status_for_error(exc)
        content: dict[str, object] = {"detail": str(exc)}
        if isinstance(exc, PartialOperationError):
            content["reconciliation_required"] = True
            if is_dataclass(exc.result):
                content["operation"] = asdict(exc.result)
        return JSONResponse(status_code=status_code, content=content)


def _status_for_error(error: ApplicationError) -> int:
    if isinstance(error, (UnknownTaskError, ImageNotFoundError)):
        return 404
    if isinstance(error, (InvalidFilenameError, UnsupportedImageTypeError)):
        return 400
    if isinstance(error, DatasetCollisionError):
        return 409
    if isinstance(error, ApprovalPersistenceError):
        return 503
    if isinstance(error, (InvalidLabelError, InvalidClassError, UnreadableImageError)):
        return 422
    if isinstance(error, (ModelUnavailableError, PartialOperationError)):
        return 500
    return 500
