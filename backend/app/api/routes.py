from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, Depends

from backend.app.core.config import Settings, get_settings
from backend.app.ml.yolo_detector import PpeDetector
from backend.app.models.schemas import ImageItem, LabelPayload, LabelResponse, OperationResponse
from backend.app.services import storage
from backend.app.services.labeling import LabelingService
from backend.app.services.visualization import VisualizationService


router = APIRouter(prefix="/api/v1")


@lru_cache
def get_detector(
    model_path: str,
    image_size: int,
    confidence: float,
    iou: float,
    use_color_vest_fallback: bool,
) -> PpeDetector:
    return PpeDetector(
        model_path=Path(model_path),
        image_size=image_size,
        confidence=confidence,
        iou=iou,
        use_color_vest_fallback=use_color_vest_fallback,
    )


def get_labeling_service(settings: Settings = Depends(get_settings)) -> LabelingService:
    return LabelingService(
        image_dir=settings.image_dir,
        label_dir=settings.label_dir,
        detector=get_detector(
            str(settings.model_path),
            settings.yolo_img_size,
            settings.yolo_conf,
            settings.yolo_iou,
            settings.use_color_vest_fallback,
        ),
    )


def get_visualization_service(settings: Settings = Depends(get_settings)) -> VisualizationService:
    return VisualizationService(
        image_dir=settings.image_dir,
        label_dir=settings.label_dir,
        visualization_dir=settings.visualization_dir,
    )


@router.get("/images", response_model=list[ImageItem])
def get_images(settings: Settings = Depends(get_settings)) -> list[ImageItem]:
    return storage.list_images(settings.image_dir, settings.label_dir, settings.visualization_dir)


@router.delete("/images/{filename}", response_model=OperationResponse)
def delete_image(filename: str, settings: Settings = Depends(get_settings)) -> OperationResponse:
    storage.delete_image_artifacts(settings.image_dir, settings.label_dir, settings.visualization_dir, filename)
    return OperationResponse(message=f"Deleted {filename}")


@router.get("/images/{filename}/labels", response_model=LabelResponse)
def get_labels(filename: str, settings: Settings = Depends(get_settings)) -> LabelResponse:
    return LabelResponse(filename=filename, boxes=storage.read_labels(settings.label_dir, filename))


@router.put("/images/{filename}/labels", response_model=OperationResponse)
def update_labels(
    filename: str,
    payload: LabelPayload,
    settings: Settings = Depends(get_settings),
) -> OperationResponse:
    storage.save_labels(settings.label_dir, filename, payload.boxes)
    return OperationResponse(message=f"Labels updated for {filename}")


@router.post("/images/{filename}/auto-label", response_model=OperationResponse)
def auto_label_image(
    filename: str,
    service: LabelingService = Depends(get_labeling_service),
) -> OperationResponse:
    box_count = service.auto_label_one(filename)
    return OperationResponse(message=f"Generated {box_count} labels for {filename}")


@router.post("/auto-label", response_model=OperationResponse)
def auto_label_all(service: LabelingService = Depends(get_labeling_service)) -> OperationResponse:
    image_count = service.auto_label_all()
    return OperationResponse(message=f"Auto-labeled {image_count} images")


@router.post("/visualizations", response_model=OperationResponse)
def generate_visualizations(
    service: VisualizationService = Depends(get_visualization_service),
) -> OperationResponse:
    generated_count = service.generate_all()
    return OperationResponse(message=f"Generated {generated_count} visualizations")
