from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from backend.app.api.dependencies import get_export_service
from backend.app.domain.models import ExportResult
from backend.app.services.export import DatasetExportService


router = APIRouter(prefix="/api/v1/tasks/{task}", tags=["exports"])


@router.get("/images/{filename}/export", response_model=None)
def export_task_image(filename: str, service: DatasetExportService = Depends(get_export_service)) -> FileResponse:
    return _export_response(service.export_image(filename))


@router.get("/export", response_model=None)
def export_task_all(service: DatasetExportService = Depends(get_export_service)) -> FileResponse:
    return _export_response(service.export_all())


def _export_response(result: ExportResult) -> FileResponse:
    return FileResponse(
        result.archive_path,
        media_type="application/zip",
        filename=result.download_name,
        background=BackgroundTask(result.archive_path.unlink, missing_ok=True),
    )
