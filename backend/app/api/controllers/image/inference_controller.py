"""PPE and safety-sign inference workspace endpoints."""

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse

from backend.app.api.dependencies.image import get_image_inference_service
from backend.app.api.schemas.image import InferenceMediaItem, OperationResponse
from backend.app.services.image_inference import ImageInferenceService


router = APIRouter(prefix="/api/v1/tasks/{task}/inference", tags=["image-inference"])


@router.get("", response_model=list[InferenceMediaItem])
def list_inference_items(service: ImageInferenceService = Depends(get_image_inference_service)) -> list[dict[str, object]]:
    return service.list_items()


@router.post("", response_model=list[InferenceMediaItem])
async def upload_inference_media(
    files: list[UploadFile] = File(...),
    service: ImageInferenceService = Depends(get_image_inference_service),
) -> list[dict[str, object]]:
    return [service.infer(file.filename or "upload", await file.read()) for file in files]


@router.get("/{item_id}/{variant}", response_class=FileResponse)
def get_inference_media(item_id: str, variant: str, service: ImageInferenceService = Depends(get_image_inference_service)) -> FileResponse:
    if variant not in {"source", "result"}:
        from backend.app.domain.errors import ImageNotFoundError
        raise ImageNotFoundError("Inference media not found")
    return FileResponse(service.media_path(item_id, variant))


@router.delete("/{item_id}", response_model=OperationResponse)
def delete_inference_item(item_id: str, service: ImageInferenceService = Depends(get_image_inference_service)) -> OperationResponse:
    service.delete(item_id)
    return OperationResponse(message="Inference item deleted")
