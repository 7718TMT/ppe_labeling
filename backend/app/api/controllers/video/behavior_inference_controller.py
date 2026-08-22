"""Read-only HTTP routes for fixed-model behavior inference."""

from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile

from backend.app.api.dependencies.video import get_behavior_inference_service
from backend.app.services.behavior_inference_service import BehaviorInferenceService


router = APIRouter(prefix="/api/v1/behavior-inference", tags=["behavior-inference"])


@router.get("")
def workspace(
    service: BehaviorInferenceService = Depends(get_behavior_inference_service),
) -> dict[str, Any]:
    """Return inference videos, jobs, and fixed-model identity."""

    return service.workspace()


@router.post("/videos")
async def import_videos(
    files: list[UploadFile] = File(...),
    service: BehaviorInferenceService = Depends(get_behavior_inference_service),
) -> list[dict[str, Any]]:
    """Import videos and queue fixed-model behavior inference."""

    return service.import_videos([
        (file.filename or "video.mp4", file.file) for file in files
    ])


@router.get("/videos/{video_id}/results")
def results(
    video_id: str,
    service: BehaviorInferenceService = Depends(get_behavior_inference_service),
) -> dict[str, Any]:
    """Return raw windows and smoothed events for one inference video."""

    return service.results(video_id)
