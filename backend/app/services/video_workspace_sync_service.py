"""Durable snapshot and delta reads for the video-labeling workspace."""

from __future__ import annotations

from typing import Any

from backend.app.repositories.video_db import VideoRepository
from backend.app.services.video_service import VideoService


class VideoWorkspaceSyncService:
    """Build compact workspace reads around the SQLite event outbox.

    This service deliberately owns no in-memory subscriber state. Both the API
    process and ``video_worker`` communicate through the repository's durable
    event rows, which means browser reconnects and process restarts can safely
    recover with an event cursor or a fresh snapshot.
    """

    def __init__(
        self,
        repository: VideoRepository,
        video_service: VideoService,
    ) -> None:
        self.repository = repository
        self.video_service = video_service

    def snapshot(self, project_id: str) -> dict[str, Any]:
        """Return the single initial read required to open a workspace."""

        # Capture the cursor first. A mutation that commits while the remaining
        # snapshot reads run has a larger event ID and will be replayed by the
        # client instead of being skipped.
        last_event_id = self.repository.latest_workspace_event_id(project_id)
        return {
            "project": self.video_service.get_project(project_id),
            "videos": self.repository.list_videos(project_id),
            "jobs": self.repository.list_jobs(project_id),
            "processing_options": self.video_service.processing_options(project_id),
            # Exports are additive to the baseline contract. Including them
            # lets the export panel stop its independent rapid polling loop.
            "exports": self.repository.list_exports(project_id),
            "last_event_id": last_event_id,
        }

    def changes(self, project_id: str, after: int) -> dict[str, Any]:
        """Return events after a cursor or an explicit resync instruction."""

        return self.repository.workspace_event_changes(project_id, after)
