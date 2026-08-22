"""FastAPI dependencies for image-annotation routes."""

from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from backend.app.core.config import Settings, TaskProfile, get_settings
from backend.app.inference.ppe_detector import PpeDetector
from backend.app.inference.safety_sign_detector import SafetySignDetector
from backend.app.repositories.approvals import ApprovalRepository
from backend.app.repositories.dataset import DatasetRepository
from backend.app.services.annotation import AnnotationService
from backend.app.services.export import DatasetExportService
from backend.app.services.media import MediaService
from backend.app.services.tasks import TaskService


def get_task_profile(task: str, settings: Settings = Depends(get_settings)) -> TaskProfile:
    """Resolve the configured image-annotation task profile."""

    return settings.task_profile(task)


@lru_cache
def get_ppe_detector(model_path: str, allowed_class_ids: tuple[int, ...], image_size: int, confidence: float, iou: float, use_color_vest_fallback: bool, device: str) -> PpeDetector:
    return PpeDetector(model_path=Path(model_path), image_size=image_size, confidence=confidence, iou=iou, allowed_class_ids=set(allowed_class_ids), use_color_vest_fallback=use_color_vest_fallback, device=device)


@lru_cache
def get_safety_sign_detector(model_path: str, allowed_class_ids: tuple[int, ...], image_size: int, confidence: float, iou: float, agnostic_nms: bool, device: str) -> SafetySignDetector:
    return SafetySignDetector(model_path=Path(model_path), allowed_class_ids=set(allowed_class_ids), image_size=image_size, confidence=confidence, iou=iou, agnostic_nms=agnostic_nms, device=device)


def get_detector(profile: TaskProfile = Depends(get_task_profile)) -> PpeDetector | SafetySignDetector:
    """Select the detector required by the active image task profile."""

    if profile.detector_type == "safety_signs":
        return get_safety_sign_detector(str(profile.model_path), tuple(profile.class_names.keys()), profile.yolo_img_size, profile.yolo_conf, profile.yolo_iou, profile.agnostic_nms, profile.inference_device)
    return get_ppe_detector(str(profile.model_path), tuple(profile.class_names.keys()), profile.yolo_img_size, profile.yolo_conf, profile.yolo_iou, profile.use_color_vest_fallback, profile.inference_device)


def get_dataset_repository(profile: TaskProfile = Depends(get_task_profile)) -> DatasetRepository:
    return DatasetRepository(profile.image_dir, profile.label_dir, profile.visualization_dir)


def get_approval_repository(settings: Settings = Depends(get_settings)) -> ApprovalRepository:
    return ApprovalRepository(settings.database_path)


def get_media_service(dataset: DatasetRepository = Depends(get_dataset_repository)) -> MediaService:
    return MediaService(dataset)


def get_export_service(profile: TaskProfile = Depends(get_task_profile), dataset: DatasetRepository = Depends(get_dataset_repository)) -> DatasetExportService:
    return DatasetExportService(profile.id, dataset)


def get_annotation_service(profile: TaskProfile = Depends(get_task_profile), dataset: DatasetRepository = Depends(get_dataset_repository), approvals: ApprovalRepository = Depends(get_approval_repository)) -> AnnotationService:
    return AnnotationService(profile.id, dataset, approvals, None, profile.class_names)


def get_inference_annotation_service(profile: TaskProfile = Depends(get_task_profile), dataset: DatasetRepository = Depends(get_dataset_repository), approvals: ApprovalRepository = Depends(get_approval_repository), detector: PpeDetector | SafetySignDetector = Depends(get_detector)) -> AnnotationService:
    return AnnotationService(profile.id, dataset, approvals, detector, profile.class_names)


def get_task_service(settings: Settings = Depends(get_settings)) -> TaskService:
    return TaskService(settings)
