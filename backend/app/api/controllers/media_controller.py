from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse

from backend.app.api.dependencies import get_media_service
from backend.app.services.media import MediaService


router = APIRouter(prefix="/media", tags=["media"])


@router.get("/{task}/images/{filename}", include_in_schema=False)
def get_task_image_file(filename: str, service: MediaService = Depends(get_media_service)) -> FileResponse:
    return FileResponse(service.image_path(filename))


@router.get("/{task}/visualizations/{filename}", include_in_schema=False)
def get_task_visualization_file(filename: str, service: MediaService = Depends(get_media_service)) -> FileResponse:
    return FileResponse(service.visualization_path(filename))
