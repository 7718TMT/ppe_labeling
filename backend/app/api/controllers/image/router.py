"""Aggregate the public image-annotation route modules."""

from fastapi import APIRouter

from backend.app.api.controllers.image import (
    annotation_controller,
    export_controller,
    media_controller,
    task_controller,
)


router = APIRouter()
router.include_router(task_controller.router)
router.include_router(annotation_controller.router)
router.include_router(export_controller.router)
router.include_router(media_controller.router)
