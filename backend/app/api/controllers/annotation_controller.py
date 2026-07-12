from fastapi import APIRouter, Depends, File, UploadFile

from backend.app.api.dependencies import get_annotation_service, get_inference_annotation_service
from backend.app.api.schemas import ApprovePayload, BoundingBox, ImageItem, LabelPayload, LabelResponse, OperationResponse
from backend.app.services.annotation import AnnotationService


router = APIRouter(prefix="/api/v1/tasks/{task}", tags=["annotation"])


@router.get("/images", response_model=list[ImageItem])
def get_task_images(task: str, service: AnnotationService = Depends(get_annotation_service)) -> list[ImageItem]:
    return [ImageItem.from_domain(image) for image in service.list_images(f"/media/{task}")]


@router.delete("/images/{filename}", response_model=OperationResponse)
def delete_task_image(filename: str, service: AnnotationService = Depends(get_annotation_service)) -> OperationResponse:
    service.delete_image(filename)
    return OperationResponse(message=f"Deleted {filename}")


@router.get("/images/{filename}/labels", response_model=LabelResponse)
def get_task_labels(filename: str, service: AnnotationService = Depends(get_annotation_service)) -> LabelResponse:
    return LabelResponse(
        filename=filename,
        boxes=[BoundingBox.from_domain(box) for box in service.read_labels(filename)],
    )


@router.post("/images/upload", response_model=OperationResponse)
async def upload_task_images(
    files: list[UploadFile] = File(...),
    service: AnnotationService = Depends(get_annotation_service),
) -> OperationResponse:
    uploads = [(file.filename or "image.jpg", await file.read()) for file in files]
    return OperationResponse(message=f"Uploaded {service.upload_images(uploads)} image(s)")


@router.put("/images/{filename}/labels", response_model=OperationResponse)
def update_task_labels(
    filename: str,
    payload: LabelPayload,
    service: AnnotationService = Depends(get_annotation_service),
) -> OperationResponse:
    service.save_labels(filename, [box.to_domain() for box in payload.boxes])
    return OperationResponse(message=f"Labels updated for {filename}")


@router.put("/images/{filename}/approve", response_model=OperationResponse)
def approve_task_image(
    filename: str,
    payload: ApprovePayload,
    service: AnnotationService = Depends(get_annotation_service),
) -> OperationResponse:
    service.set_approval(filename, payload.is_approved)
    return OperationResponse(message=f"Approval set to {payload.is_approved} for {filename}")


@router.post("/rename-sequential", response_model=OperationResponse)
def rename_task_sequential(service: AnnotationService = Depends(get_annotation_service)) -> OperationResponse:
    result = service.rename_dataset_sequential()
    return OperationResponse(message=f"Renamed {result.count} image(s)")


@router.post("/images/{filename}/auto-label", response_model=OperationResponse)
def auto_label_task_image(filename: str, service: AnnotationService = Depends(get_inference_annotation_service)) -> OperationResponse:
    return OperationResponse(message=f"Generated {service.auto_label_one(filename)} labels for {filename}")


@router.post("/auto-label", response_model=OperationResponse)
def auto_label_task_all(service: AnnotationService = Depends(get_inference_annotation_service)) -> OperationResponse:
    return OperationResponse(message=f"Auto-labeled {service.auto_label_all()} images")


@router.post("/visualizations", response_model=OperationResponse)
def generate_task_visualizations(service: AnnotationService = Depends(get_annotation_service)) -> OperationResponse:
    return OperationResponse(message=f"Generated {service.generate_visualizations()} visualizations")
