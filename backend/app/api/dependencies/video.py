"""FastAPI dependencies for video-labeling routes."""

from functools import lru_cache
from pathlib import Path

from fastapi import Depends

from backend.app.core.config import Settings, get_settings
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.behavior_inference_service import BehaviorInferenceService
from backend.app.services.video_annotation_service import VideoAnnotationService
from backend.app.services.video_export_service import VideoExportService
from backend.app.services.video_feature_service import VideoFeatureService
from backend.app.services.video_model_service import VideoModelService
from backend.app.services.video_service import VideoService
from backend.app.services.video_workspace_sync_service import VideoWorkspaceSyncService


@lru_cache
def _video_repository(database_path: str) -> VideoRepository:
    return VideoRepository(Path(database_path))


@lru_cache
def _video_storage(root: str) -> VideoStorageRepository:
    return VideoStorageRepository(Path(root))


def get_video_repository(settings: Settings = Depends(get_settings)) -> VideoRepository:
    return _video_repository(str(settings.database_path))


def get_video_storage(settings: Settings = Depends(get_settings)) -> VideoStorageRepository:
    return _video_storage(str(settings.video_storage_root))


def get_video_service(repository: VideoRepository = Depends(get_video_repository), storage: VideoStorageRepository = Depends(get_video_storage)) -> VideoService:
    return VideoService(repository, storage)


def get_video_workspace_sync_service(repository: VideoRepository = Depends(get_video_repository), video_service: VideoService = Depends(get_video_service)) -> VideoWorkspaceSyncService:
    """Provide snapshot/delta sync reads backed by the durable video outbox."""

    return VideoWorkspaceSyncService(repository, video_service)


def get_video_annotation_service(repository: VideoRepository = Depends(get_video_repository), storage: VideoStorageRepository = Depends(get_video_storage)) -> VideoAnnotationService:
    return VideoAnnotationService(repository, storage)


def get_video_feature_service(repository: VideoRepository = Depends(get_video_repository), storage: VideoStorageRepository = Depends(get_video_storage)) -> VideoFeatureService:
    return VideoFeatureService(repository, storage)


def get_video_model_service(
    repository: VideoRepository = Depends(get_video_repository),
    storage: VideoStorageRepository = Depends(get_video_storage),
    features: VideoFeatureService = Depends(get_video_feature_service),
    settings: Settings = Depends(get_settings),
) -> VideoModelService:
    return VideoModelService(repository, storage, features, settings.inference_device)


def get_video_export_service(repository: VideoRepository = Depends(get_video_repository), storage: VideoStorageRepository = Depends(get_video_storage), features: VideoFeatureService = Depends(get_video_feature_service)) -> VideoExportService:
    return VideoExportService(repository, storage, features)


def get_behavior_inference_service(
    repository: VideoRepository = Depends(get_video_repository),
    storage: VideoStorageRepository = Depends(get_video_storage),
    settings: Settings = Depends(get_settings),
) -> BehaviorInferenceService:
    """Provide the fixed-model, read-only behavior inference workflow."""

    return BehaviorInferenceService(repository, storage, settings.behavior_model_path)
