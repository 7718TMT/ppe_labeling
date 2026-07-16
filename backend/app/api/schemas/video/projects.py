"""Project and managed-video request contracts."""

from backend.app.api.schemas.video.contracts import (
    ProjectConfigUpdate,
    ProjectCreate,
    VideoDeleteResponse,
    VideoRenamePayload,
    VideoTrimPayload,
)

__all__ = [
    "ProjectConfigUpdate", "ProjectCreate", "VideoDeleteResponse",
    "VideoRenamePayload", "VideoTrimPayload",
]
