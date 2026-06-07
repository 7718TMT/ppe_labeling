from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.app.api.routes import router
from backend.app.core.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="PPE Labeling API")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(router)
    app.mount("/media/images", StaticFiles(directory=settings.image_dir), name="images")
    app.mount(
        "/media/visualizations",
        StaticFiles(directory=settings.visualization_dir),
        name="visualizations",
    )

    return app


app = create_app()
