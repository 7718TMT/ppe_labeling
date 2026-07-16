from fastapi import APIRouter

from backend.app.api.controllers.image.router import router as image_router
from backend.app.api.controllers.video.router import router as video_router


router = APIRouter()
router.include_router(image_router)
router.include_router(video_router)
