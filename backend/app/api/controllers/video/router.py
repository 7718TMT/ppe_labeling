"""Aggregate public video-labeling and behavior-inference routes."""

from fastapi import APIRouter

from backend.app.api.controllers.video.behavior_inference_controller import (
    router as inference_router,
)
from backend.app.api.controllers.video.controller import router as labeling_router


router = APIRouter()
router.include_router(labeling_router)
router.include_router(inference_router)
