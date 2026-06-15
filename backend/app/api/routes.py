from functools import lru_cache
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from fastapi import APIRouter, Depends, File, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.core.config import Settings, TaskProfile, get_settings
from backend.app.ml.safety_sign_detector import SafetySignDetector
from backend.app.ml.yolo_detector import PpeDetector
from backend.app.models.schemas import ImageItem, LabelPayload, LabelResponse, OperationResponse, TaskInfo
from backend.app.services import storage
from backend.app.services.labeling import LabelingService
from backend.app.services.visualization import VisualizationService


router = APIRouter(prefix="/api/v1")
media_router = APIRouter(prefix="/media")


@lru_cache
def get_ppe_detector(
    model_path: str,
    allowed_class_ids: tuple[int, ...],
    image_size: int,
    confidence: float,
    iou: float,
    use_color_vest_fallback: bool,
    device: str,
) -> PpeDetector:
    return PpeDetector(
        model_path=Path(model_path),
        image_size=image_size,
        confidence=confidence,
        iou=iou,
        allowed_class_ids=set(allowed_class_ids),
        use_color_vest_fallback=use_color_vest_fallback,
        device=device,
    )


@lru_cache
def get_safety_sign_detector(
    model_path: str,
    allowed_class_ids: tuple[int, ...],
    image_size: int,
    confidence: float,
    iou: float,
    agnostic_nms: bool,
    device: str,
) -> SafetySignDetector:
    return SafetySignDetector(
        model_path=Path(model_path),
        allowed_class_ids=set(allowed_class_ids),
        image_size=image_size,
        confidence=confidence,
        iou=iou,
        agnostic_nms=agnostic_nms,
        device=device,
    )


def get_task_profile(task: str, settings: Settings = Depends(get_settings)) -> TaskProfile:
    return settings.task_profile(task)


def detector_for_profile(profile: TaskProfile):
    if profile.detector_type == "safety_signs":
        return get_safety_sign_detector(
            str(profile.model_path),
            tuple(profile.class_names.keys()),
            profile.yolo_img_size,
            profile.yolo_conf,
            profile.yolo_iou,
            profile.agnostic_nms,
            profile.inference_device,
        )

    return get_ppe_detector(
        str(profile.model_path),
        tuple(profile.class_names.keys()),
        profile.yolo_img_size,
        profile.yolo_conf,
        profile.yolo_iou,
        profile.use_color_vest_fallback,
        profile.inference_device,
    )


def labeling_service_for_profile(profile: TaskProfile) -> LabelingService:
    return LabelingService(
        image_dir=profile.image_dir,
        label_dir=profile.label_dir,
        detector=detector_for_profile(profile),
    )


def visualization_service_for_profile(profile: TaskProfile) -> VisualizationService:
    return VisualizationService(
        image_dir=profile.image_dir,
        label_dir=profile.label_dir,
        visualization_dir=profile.visualization_dir,
        class_names=profile.class_names,
    )


@router.get("/tasks", response_model=list[TaskInfo])
def get_tasks(settings: Settings = Depends(get_settings)) -> list[TaskInfo]:
    return [
        TaskInfo(
            id=profile.id,
            name=profile.name,
            class_names=profile.class_names,
            temporary_class_id=profile.temporary_class_id,
        )
        for profile in settings.task_profiles.values()
    ]


@router.get("/tasks/{task}/images", response_model=list[ImageItem])
def get_task_images(profile: TaskProfile = Depends(get_task_profile)) -> list[ImageItem]:
    return storage.list_images(
        profile.image_dir,
        profile.label_dir,
        profile.visualization_dir,
        media_prefix=f"/media/{profile.id}",
    )


@router.delete("/tasks/{task}/images/{filename}", response_model=OperationResponse)
def delete_task_image(filename: str, profile: TaskProfile = Depends(get_task_profile)) -> OperationResponse:
    storage.delete_image_artifacts(profile.image_dir, profile.label_dir, profile.visualization_dir, filename)
    return OperationResponse(message=f"Deleted {filename}")


@router.get("/tasks/{task}/images/{filename}/labels", response_model=LabelResponse)
def get_task_labels(filename: str, profile: TaskProfile = Depends(get_task_profile)) -> LabelResponse:
    return LabelResponse(filename=filename, boxes=storage.read_labels(profile.label_dir, filename))


@router.post("/tasks/{task}/images/upload", response_model=OperationResponse)
async def upload_task_images(
    files: list[UploadFile] = File(...),
    profile: TaskProfile = Depends(get_task_profile),
) -> OperationResponse:
    uploaded_names: list[str] = []
    for file in files:
        content = await file.read()
        uploaded_names.append(storage.save_uploaded_image(profile.image_dir, file.filename or "image.jpg", content))
    return OperationResponse(message=f"Uploaded {len(uploaded_names)} image(s)")


@router.put("/tasks/{task}/images/{filename}/labels", response_model=OperationResponse)
def update_task_labels(
    filename: str,
    payload: LabelPayload,
    profile: TaskProfile = Depends(get_task_profile),
) -> OperationResponse:
    storage.validate_label_classes(payload.boxes, set(profile.class_names))
    storage.save_labels(profile.label_dir, filename, payload.boxes)
    return OperationResponse(message=f"Labels updated for {filename}")


@router.get("/tasks/{task}/images/{filename}/export", response_model=None)
def export_task_image(filename: str, profile: TaskProfile = Depends(get_task_profile)) -> StreamingResponse:
    return export_zip_response(profile, [filename], f"{Path(filename).stem}_dataset.zip")


@router.get("/tasks/{task}/export", response_model=None)
def export_task_all(profile: TaskProfile = Depends(get_task_profile)) -> StreamingResponse:
    filenames = [path.name for path in storage.image_paths(profile.image_dir)]
    return export_zip_response(profile, filenames, f"{profile.id}_dataset.zip")


@router.post("/tasks/{task}/rename-sequential", response_model=OperationResponse)
def rename_task_sequential(profile: TaskProfile = Depends(get_task_profile)) -> OperationResponse:
    renamed_count = storage.rename_dataset_sequential(profile.image_dir, profile.label_dir, profile.visualization_dir)
    return OperationResponse(message=f"Renamed {renamed_count} image(s)")


@router.post("/tasks/{task}/images/{filename}/auto-label", response_model=OperationResponse)
def auto_label_task_image(
    filename: str,
    profile: TaskProfile = Depends(get_task_profile),
) -> OperationResponse:
    service = labeling_service_for_profile(profile)
    box_count = service.auto_label_one(filename)
    return OperationResponse(message=f"Generated {box_count} labels for {filename}")


@router.post("/tasks/{task}/auto-label", response_model=OperationResponse)
def auto_label_task_all(profile: TaskProfile = Depends(get_task_profile)) -> OperationResponse:
    service = labeling_service_for_profile(profile)
    image_count = service.auto_label_all()
    return OperationResponse(message=f"Auto-labeled {image_count} images")


@router.post("/tasks/{task}/visualizations", response_model=OperationResponse)
def generate_task_visualizations(profile: TaskProfile = Depends(get_task_profile)) -> OperationResponse:
    service = visualization_service_for_profile(profile)
    generated_count = service.generate_all()
    return OperationResponse(message=f"Generated {generated_count} visualizations")


def export_zip_response(profile: TaskProfile, filenames: list[str], download_name: str) -> StreamingResponse:
    buffer = BytesIO()
    with ZipFile(buffer, mode="w", compression=ZIP_DEFLATED) as zip_file:
        for filename in filenames:
            storage.copy_image_and_label_to_zip(zip_file, profile.image_dir, profile.label_dir, filename)
    buffer.seek(0)
    return StreamingResponse(
        buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{download_name}"'},
    )


@media_router.get("/{task}/images/{filename}", include_in_schema=False)
def get_task_image_file(filename: str, profile: TaskProfile = Depends(get_task_profile)) -> FileResponse:
    storage.validate_image_filename(filename)
    return FileResponse(profile.image_dir / filename)


@media_router.get("/{task}/visualizations/{filename}", include_in_schema=False)
def get_task_visualization_file(filename: str, profile: TaskProfile = Depends(get_task_profile)) -> FileResponse:
    storage.validate_image_filename(filename.replace("verified_", "", 1))
    return FileResponse(profile.visualization_dir / filename)


def active_profile(settings: Settings) -> TaskProfile:
    return settings.task_profile(settings.active_task)


@router.get("/images", response_model=list[ImageItem])
def get_images(settings: Settings = Depends(get_settings)) -> list[ImageItem]:
    profile = active_profile(settings)
    return storage.list_images(profile.image_dir, profile.label_dir, profile.visualization_dir, media_prefix=f"/media/{profile.id}")


@router.delete("/images/{filename}", response_model=OperationResponse)
def delete_image(filename: str, settings: Settings = Depends(get_settings)) -> OperationResponse:
    profile = active_profile(settings)
    storage.delete_image_artifacts(profile.image_dir, profile.label_dir, profile.visualization_dir, filename)
    return OperationResponse(message=f"Deleted {filename}")


@router.get("/images/{filename}/labels", response_model=LabelResponse)
def get_labels(filename: str, settings: Settings = Depends(get_settings)) -> LabelResponse:
    profile = active_profile(settings)
    return LabelResponse(filename=filename, boxes=storage.read_labels(profile.label_dir, filename))


@router.put("/images/{filename}/labels", response_model=OperationResponse)
def update_labels(filename: str, payload: LabelPayload, settings: Settings = Depends(get_settings)) -> OperationResponse:
    profile = active_profile(settings)
    storage.validate_label_classes(payload.boxes, set(profile.class_names))
    storage.save_labels(profile.label_dir, filename, payload.boxes)
    return OperationResponse(message=f"Labels updated for {filename}")


@router.post("/images/{filename}/auto-label", response_model=OperationResponse)
def auto_label_image(filename: str, settings: Settings = Depends(get_settings)) -> OperationResponse:
    service = labeling_service_for_profile(active_profile(settings))
    box_count = service.auto_label_one(filename)
    return OperationResponse(message=f"Generated {box_count} labels for {filename}")


@router.post("/auto-label", response_model=OperationResponse)
def auto_label_all(settings: Settings = Depends(get_settings)) -> OperationResponse:
    service = labeling_service_for_profile(active_profile(settings))
    image_count = service.auto_label_all()
    return OperationResponse(message=f"Auto-labeled {image_count} images")


@router.post("/visualizations", response_model=OperationResponse)
def generate_visualizations(settings: Settings = Depends(get_settings)) -> OperationResponse:
    service = visualization_service_for_profile(active_profile(settings))
    generated_count = service.generate_all()
    return OperationResponse(message=f"Generated {generated_count} visualizations")
