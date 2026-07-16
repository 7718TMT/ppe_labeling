"""Thin HTTP controller for pose-video labeling APIs."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from time import monotonic
from typing import Any, AsyncIterator

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse

from backend.app.api.dependencies import (
    get_video_annotation_service,
    get_video_export_service,
    get_video_feature_service,
    get_video_model_service,
    get_video_service,
    get_video_workspace_sync_service,
)
from backend.app.api.video_schemas import (
    AnnotationDerivativeRefreshResponse,
    InclusionPayload,
    JobControl,
    ProcessRequest,
    ProcessingJobResponse,
    ProcessingOptionsResponse,
    ProjectConfigUpdate,
    ProjectCreate,
    QueueRequest,
    ReassignPayload,
    RevisionPayload,
    SegmentMergePayload,
    SegmentInclusionPayload,
    SegmentSplitPayload,
    SegmentWrite,
    ThresholdProfilePayload,
    TrackMergeMultiplePayload,
    TrackMergePayload,
    TrackSplitPayload,
    VideoDeleteResponse,
    VideoRenamePayload,
    VideoTrimPayload,
    WindowReviewPayload,
    WorkspaceStatePayload,
    WorkspaceChangesResponse,
    WorkspaceSnapshotResponse,
)
from backend.app.services.video_annotation_service import VideoAnnotationService
from backend.app.services.video_export_service import VideoExportService
from backend.app.services.video_feature_service import VideoFeatureService
from backend.app.services.video_model_service import VideoModelService
from backend.app.services.video_service import VideoService
from backend.app.services.video_workspace_sync_service import VideoWorkspaceSyncService


router = APIRouter(prefix="/api/v1/video-projects", tags=["video-labeling"])

SSE_POLL_SECONDS = 0.5
SSE_HEARTBEAT_SECONDS = 15.0


def _sse_message(event_type: str, payload: dict[str, Any]) -> str:
    """Encode one standards-compliant server-sent event message."""

    event_id = payload.get("event_id")
    lines = []
    if event_id is not None:
        lines.append(f"id: {event_id}")
    lines.append(f"event: {event_type}")
    lines.append(
        "data: " + json.dumps(payload, separators=(",", ":"), sort_keys=True)
    )
    return "\n".join(lines) + "\n\n"


def _event_cursor(request: Request, after: int) -> int:
    """Prefer EventSource's reconnect cursor when the browser supplies it."""

    header = request.headers.get("last-event-id")
    if header is None:
        return after
    try:
        parsed = int(header)
    except ValueError:
        return after
    return parsed if parsed >= 0 else after


@router.post("")
def create_project(payload: ProjectCreate, service: VideoService = Depends(get_video_service)) -> dict[str, Any]:
    return service.create_project(payload.name, payload.config)


@router.get("")
def list_projects(service: VideoService = Depends(get_video_service)) -> list[dict[str, Any]]:
    return service.list_projects()


@router.get("/{project_id}")
def get_project(project_id: str, service: VideoService = Depends(get_video_service)) -> dict[str, Any]:
    return service.get_project(project_id)


@router.get(
    "/{project_id}/workspace-snapshot",
    response_model=WorkspaceSnapshotResponse,
)
def workspace_snapshot(
    project_id: str,
    service: VideoWorkspaceSyncService = Depends(get_video_workspace_sync_service),
) -> dict[str, Any]:
    """Return the one initial state read required to open a workspace."""

    return service.snapshot(project_id)


@router.get(
    "/{project_id}/workspace-changes",
    response_model=WorkspaceChangesResponse,
)
def workspace_changes(
    project_id: str,
    after: int = Query(default=0, ge=0),
    service: VideoWorkspaceSyncService = Depends(get_video_workspace_sync_service),
) -> dict[str, Any]:
    """Return a compact durable event delta for fallback synchronization."""

    return service.changes(project_id, after)


@router.get("/{project_id}/events")
async def workspace_events(
    project_id: str,
    request: Request,
    after: int = Query(default=0, ge=0),
    service: VideoWorkspaceSyncService = Depends(get_video_workspace_sync_service),
) -> StreamingResponse:
    """Stream durable workspace events, with cursor-based reconnection support.

    HTTP mutations remain REST calls. SSE is intentionally one-way: it removes
    repeated full-project polling while retaining standard EventSource retries.
    """

    # Validate project ownership before returning a long-lived response so a
    # missing project is a normal 404 rather than a silent closed stream.
    service.repository.get_project(project_id)
    cursor = _event_cursor(request, after)

    async def stream() -> AsyncIterator[str]:
        nonlocal cursor
        last_heartbeat = monotonic()
        while True:
            if await request.is_disconnected():
                return
            # Repository reads use SQLite's synchronous driver. Offload the
            # short delta read so a busy database never blocks unrelated ASGI
            # requests while this long-lived response is open.
            changes = await asyncio.to_thread(service.changes, project_id, cursor)
            if changes["resync_required"]:
                resync_event = {
                    "event_id": int(changes["last_event_id"]),
                    "project_id": project_id,
                    "video_id": None,
                    "event_type": "resync.required",
                    "payload": {
                        "last_event_id": int(changes["last_event_id"]),
                        "resync_required": True,
                    },
                    "created_at": datetime.now(timezone.utc).isoformat(),
                }
                yield _sse_message(
                    "resync.required",
                    resync_event,
                )
                return
            for event in changes["events"]:
                cursor = int(event["event_id"])
                yield _sse_message(str(event["event_type"]), event)
            if changes["has_more"]:
                # Drain large backlogs without an artificial polling delay.
                continue
            now = monotonic()
            if now - last_heartbeat >= SSE_HEARTBEAT_SECONDS:
                yield ": keep-alive\n\n"
                last_heartbeat = now
            await asyncio.sleep(SSE_POLL_SECONDS)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.put("/{project_id}/config")
def update_project(project_id: str, payload: ProjectConfigUpdate, service: VideoService = Depends(get_video_service)) -> dict[str, Any]:
    return service.update_project(project_id, payload.config)


@router.post("/{project_id}/videos/import")
def import_videos(
    project_id: str,
    files: list[UploadFile] = File(...),
    mode: str = "threshold",
    service: VideoService = Depends(get_video_service),
) -> list[dict[str, Any]]:
    """Import videos and immediately queue the processing pipeline.

    The ``mode`` parameter (``threshold`` or ``model``) controls which suggestion
    source is generated after pose tracking completes. Defaults to ``threshold``.
    """
    imported = [service.import_video(project_id, file.filename or "video.mp4", file.file) for file in files]
    # Auto-queue pipeline for each newly imported video using the chosen mode.
    for video in imported:
        try:
            service.queue_pipeline(project_id, video["video_id"], mode, priority=500)
        except Exception:  # noqa: BLE001 – import must not fail if queue fails
            pass
    return imported


@router.get("/{project_id}/videos")
def list_videos(
    project_id: str,
    status: str | None = Query(default=None),
    service: VideoService = Depends(get_video_service),
) -> list[dict[str, Any]]:
    return service.list_videos(project_id, status)


@router.get("/{project_id}/videos/{video_id}")
def get_video(project_id: str, video_id: str, service: VideoService = Depends(get_video_service)) -> dict[str, Any]:
    return service.get_video(project_id, video_id)


@router.get("/{project_id}/videos/{video_id}/media")
def video_media(project_id: str, video_id: str, service: VideoService = Depends(get_video_service)) -> FileResponse:
    path, media_type = service.media(project_id, video_id)
    return FileResponse(path, media_type=media_type, content_disposition_type="inline")


@router.get("/{project_id}/videos/{video_id}/thumbnail")
def video_thumbnail(
    project_id: str,
    video_id: str,
    service: VideoService = Depends(get_video_service),
) -> FileResponse:
    path, fallback = service.thumbnail(project_id, video_id)
    return FileResponse(
        path,
        media_type="image/jpeg",
        content_disposition_type="inline",
        headers={"X-Thumbnail-Fallback": str(fallback).lower()},
    )


@router.delete(
    "/{project_id}/videos/{video_id}",
    response_model=VideoDeleteResponse,
)
def delete_video(
    project_id: str,
    video_id: str,
    service: VideoService = Depends(get_video_service),
) -> dict[str, Any]:
    return service.delete_video(project_id, video_id)


@router.post("/{project_id}/videos/rename")
def rename_videos(
    project_id: str,
    payload: VideoRenamePayload,
    service: VideoService = Depends(get_video_service),
) -> list[dict[str, Any]]:
    """Rename every video display name in a project with one prefix."""

    return service.rename_videos(project_id, payload.prefix)


@router.post("/{project_id}/videos/{video_id}/trim")
def trim_video(
    project_id: str,
    video_id: str,
    payload: VideoTrimPayload,
    service: VideoService = Depends(get_video_service),
) -> dict[str, Any]:
    """Persist a frame-accurate trim as either a replacement or a new video."""

    return service.trim_video(
        project_id,
        video_id,
        payload.start_frame,
        payload.end_frame,
        payload.save_mode,
        payload.filename,
        payload.suggestion_mode,
    )


@router.get("/{project_id}/videos/{video_id}/overlay")
def video_overlay(
    project_id: str, video_id: str, start: int = Query(ge=0), end: int = Query(ge=0),
    service: VideoService = Depends(get_video_service),
) -> list[dict[str, Any]]:
    return service.overlay_range(project_id, video_id, start, end)


@router.put("/{project_id}/videos/{video_id}/inclusion")
def set_video_inclusion(project_id: str, video_id: str, payload: InclusionPayload, service: VideoService = Depends(get_video_service)) -> dict[str, Any]:
    return service.set_video_inclusion(video_id, payload.include, payload.reason)


@router.post(
    "/{project_id}/videos/{video_id}/queue",
    response_model=list[ProcessingJobResponse],
)
def queue_video(project_id: str, video_id: str, payload: QueueRequest, service: VideoService = Depends(get_video_service)) -> list[dict[str, Any]]:
    return service.queue_pipeline(
        project_id,
        video_id,
        "threshold",
        payload.priority,
    )


@router.post(
    "/{project_id}/videos/{video_id}/process",
    response_model=list[ProcessingJobResponse],
)
def process_video(
    project_id: str,
    video_id: str,
    payload: ProcessRequest,
    service: VideoService = Depends(get_video_service),
) -> list[dict[str, Any]]:
    return service.queue_pipeline(
        project_id,
        video_id,
        payload.mode,
        payload.priority,
        payload.overwrite_labels,
    )


@router.post(
    "/{project_id}/videos/{video_id}/annotation-derivatives/refresh",
    response_model=AnnotationDerivativeRefreshResponse,
)
def refresh_annotation_derivatives(
    project_id: str,
    video_id: str,
    service: VideoService = Depends(get_video_service),
) -> dict[str, Any]:
    """Refresh training/export derivatives without generating suggestions."""

    return service.refresh_annotation_derivatives(project_id, video_id)


@router.get(
    "/{project_id}/processing-options",
    response_model=ProcessingOptionsResponse,
)
def processing_options(
    project_id: str,
    service: VideoService = Depends(get_video_service),
) -> dict[str, Any]:
    return service.processing_options(project_id)


@router.get("/{project_id}/jobs", response_model=list[ProcessingJobResponse])
def list_jobs(project_id: str, service: VideoService = Depends(get_video_service)) -> list[dict[str, Any]]:
    return service.list_jobs(project_id)


@router.post(
    "/{project_id}/jobs/{job_id}/control",
    response_model=ProcessingJobResponse,
)
def control_job(project_id: str, job_id: str, payload: JobControl, service: VideoService = Depends(get_video_service)) -> dict[str, Any]:
    return service.control_job(job_id, payload.action)


@router.get("/{project_id}/videos/{video_id}/tracks")
def list_tracks(project_id: str, video_id: str, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> list[dict[str, Any]]:
    return service.list_tracks(video_id)


@router.post("/{project_id}/videos/{video_id}/tracks/{track_id}/merge")
def merge_track(
    project_id: str,
    video_id: str,
    track_id: int,
    payload: TrackMergePayload,
    service: VideoAnnotationService = Depends(get_video_annotation_service),
) -> dict[str, Any]:
    """Merge ``source_track_id`` into ``track_id``."""
    return service.merge_tracks(video_id, track_id, payload.source_track_id)


@router.post("/{project_id}/videos/{video_id}/tracks/merge-multiple")
def merge_multiple_tracks(
    project_id: str,
    video_id: str,
    payload: TrackMergeMultiplePayload,
    service: VideoAnnotationService = Depends(get_video_annotation_service),
) -> dict[str, Any]:
    """Merge all tracks listed in ``track_ids`` into the first one."""
    return service.merge_multiple_tracks(video_id, payload.track_ids)


@router.post("/{project_id}/videos/{video_id}/tracks/{track_id}/split")
def split_track(project_id: str, video_id: str, track_id: int, payload: TrackSplitPayload, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> list[dict[str, Any]]:
    return service.split_track(video_id, track_id, payload.frame)


@router.put("/{project_id}/videos/{video_id}/tracks/{track_id}/inclusion")
def set_track_inclusion(project_id: str, video_id: str, track_id: int, payload: InclusionPayload, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    return service.set_track_inclusion(video_id, track_id, payload.include, payload.reason)


@router.delete("/{project_id}/videos/{video_id}/tracks/{track_id}")
def delete_track(project_id: str, video_id: str, track_id: int, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    return service.delete_track(video_id, track_id)


@router.get("/{project_id}/videos/{video_id}/segments")
def list_segments(project_id: str, video_id: str, track_id: int | None = None, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    return service.segment_snapshot(video_id, track_id)


@router.post("/{project_id}/videos/{video_id}/segments")
def create_segment(project_id: str, video_id: str, payload: SegmentWrite, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    return service.save_segment(video_id, payload.track_id, payload.start_frame, payload.end_frame, payload.label, payload.expected_revision)


@router.put("/{project_id}/videos/{video_id}/segments/{segment_id}")
def update_segment(project_id: str, video_id: str, segment_id: str, payload: SegmentWrite, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    return service.save_segment(video_id, payload.track_id, payload.start_frame, payload.end_frame, payload.label, payload.expected_revision, segment_id)


@router.delete("/{project_id}/videos/{video_id}/segments/{segment_id}")
def delete_segment(project_id: str, video_id: str, segment_id: str, payload: RevisionPayload, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    return {"revision": service.delete_segment(video_id, segment_id, payload.expected_revision)}


@router.put("/{project_id}/videos/{video_id}/segments/{segment_id}/inclusion")
def set_segment_inclusion(project_id: str, video_id: str, segment_id: str, payload: SegmentInclusionPayload, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    return service.set_segment_inclusion(video_id, segment_id, payload.include, payload.reason, payload.expected_revision)


@router.post("/{project_id}/videos/{video_id}/segments/{segment_id}/split")
def split_segment(project_id: str, video_id: str, segment_id: str, payload: SegmentSplitPayload, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> list[dict[str, Any]]:
    return service.split_segment(video_id, segment_id, payload.frame, payload.expected_revision)


@router.post("/{project_id}/videos/{video_id}/segments/merge")
def merge_segments(project_id: str, video_id: str, payload: SegmentMergePayload, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    return service.merge_segments(video_id, payload.segment_ids, payload.expected_revision)


@router.post("/{project_id}/videos/{video_id}/segments/{segment_id}/reassign")
def reassign_segment(project_id: str, video_id: str, segment_id: str, payload: ReassignPayload, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    return service.reassign_segment(video_id, segment_id, payload.target_track_id, payload.expected_revision)


@router.post("/{project_id}/videos/{video_id}/segments/{segment_id}/extend")
def extend_segment(project_id: str, video_id: str, segment_id: str, payload: RevisionPayload, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    return service.extend_segment(video_id, segment_id, payload.expected_revision)


@router.post("/{project_id}/videos/{video_id}/tracks/{track_id}/label/{label}")
def label_full_track(project_id: str, video_id: str, track_id: int, label: str, payload: RevisionPayload, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    return service.label_full_track(video_id, track_id, label, payload.expected_revision)


@router.post("/{project_id}/videos/{video_id}/history/{action}")
def history_action(project_id: str, video_id: str, action: str, payload: RevisionPayload, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    if action == "undo":
        return {"revision": service.undo(video_id, payload.expected_revision)}
    if action == "redo":
        return {"revision": service.redo(video_id, payload.expected_revision)}
    from backend.app.domain.errors import VideoValidationError
    raise VideoValidationError("History action must be undo or redo")


@router.get("/{project_id}/videos/{video_id}/validate")
def validate_video(project_id: str, video_id: str, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> dict[str, Any]:
    errors = service.validate_video(video_id)
    return {"valid": not errors, "errors": errors}


@router.post("/{project_id}/videos/{video_id}/approve")
def approve_video(
    project_id: str,
    video_id: str,
    service: VideoAnnotationService = Depends(get_video_annotation_service),
) -> dict[str, Any]:
    """Mark a video as approved after validation."""
    return service.approve(video_id)


@router.post("/{project_id}/videos/{video_id}/unapprove")
def unapprove_video(
    project_id: str,
    video_id: str,
    service: VideoAnnotationService = Depends(get_video_annotation_service),
) -> dict[str, Any]:
    """Revoke approval so a video can be re-annotated."""
    return service.unapprove(video_id)


@router.get("/{project_id}/videos/{video_id}/history")
def annotation_history(project_id: str, video_id: str, service: VideoAnnotationService = Depends(get_video_annotation_service)) -> list[dict[str, Any]]:
    return service.history(video_id)


@router.post("/{project_id}/videos/{video_id}/windows/generate")
def generate_windows(project_id: str, video_id: str, service: VideoFeatureService = Depends(get_video_feature_service)) -> list[dict[str, Any]]:
    return service.generate_windows(video_id)


@router.get("/{project_id}/videos/{video_id}/windows")
def list_windows(project_id: str, video_id: str, track_id: int | None = None, service: VideoFeatureService = Depends(get_video_feature_service)) -> list[dict[str, Any]]:
    return service.list_windows(video_id, track_id)


@router.put("/{project_id}/videos/{video_id}/windows/{window_id}")
def review_window(project_id: str, video_id: str, window_id: str, payload: WindowReviewPayload, service: VideoFeatureService = Depends(get_video_feature_service)) -> dict[str, Any]:
    return service.review_window(video_id, window_id, payload.include, payload.reason)


@router.post("/{project_id}/videos/{video_id}/features/generate")
def generate_features(project_id: str, video_id: str, service: VideoFeatureService = Depends(get_video_feature_service)) -> dict[str, Any]:
    return service.extract_features(video_id)


@router.get("/{project_id}/videos/{video_id}/features")
def inspect_features(project_id: str, video_id: str, track_id: int | None = None, start: int | None = None, end: int | None = None, service: VideoFeatureService = Depends(get_video_feature_service)) -> list[dict[str, Any]]:
    return service.feature_range(video_id, track_id, start, end)


@router.get("/{project_id}/threshold-profiles")
def list_profiles(project_id: str, service: VideoFeatureService = Depends(get_video_feature_service)) -> list[dict[str, Any]]:
    return service.list_profiles(project_id)


@router.post("/{project_id}/threshold-profiles")
def save_profile(project_id: str, payload: ThresholdProfilePayload, service: VideoFeatureService = Depends(get_video_feature_service)) -> dict[str, Any]:
    return service.save_profile(project_id, payload.name, payload.config, payload.profile_id)


@router.post("/{project_id}/threshold-profiles/restore-default")
def restore_profile(project_id: str, service: VideoFeatureService = Depends(get_video_feature_service)) -> dict[str, Any]:
    return service.restore_default_profile(project_id)


@router.post("/{project_id}/models/import")
def import_model(
    project_id: str,
    artifact: UploadFile = File(...), manifest_json: str = Form(...), trusted_local: bool = Form(False),
    service: VideoModelService = Depends(get_video_model_service),
) -> dict[str, Any]:
    return service.import_model(project_id, artifact.filename or "model.joblib", artifact.file, json.loads(manifest_json), trusted_local)


@router.get("/{project_id}/models")
def list_models(project_id: str, service: VideoModelService = Depends(get_video_model_service)) -> list[dict[str, Any]]:
    return service.list_models(project_id)


@router.post("/{project_id}/models/{model_id}/activate")
def activate_model(project_id: str, model_id: str, service: VideoModelService = Depends(get_video_model_service)) -> dict[str, Any]:
    return service.activate_model(project_id, model_id)


@router.post("/{project_id}/models/{model_id}/unload")
def unload_model(project_id: str, model_id: str, service: VideoModelService = Depends(get_video_model_service)) -> dict[str, Any]:
    return service.deactivate_model(project_id, model_id)


@router.post("/{project_id}/videos/{video_id}/models/{model_id}/infer")
def infer_model(project_id: str, video_id: str, model_id: str, service: VideoModelService = Depends(get_video_model_service)) -> dict[str, Any]:
    return service.queue_inference(project_id, video_id, model_id)


@router.get("/{project_id}/exports/validate")
def validate_export(project_id: str, service: VideoExportService = Depends(get_video_export_service)) -> dict[str, list[str]]:
    return service.validate(project_id)


@router.post("/{project_id}/exports")
def create_export(project_id: str, service: VideoExportService = Depends(get_video_export_service)) -> dict[str, Any]:
    return service.queue(project_id)


@router.get("/{project_id}/exports")
def list_exports(project_id: str, service: VideoExportService = Depends(get_video_export_service)) -> list[dict[str, Any]]:
    return service.list_exports(project_id)


@router.get("/{project_id}/exports/{export_id}/files/{filename}")
def download_export(project_id: str, export_id: str, filename: str, service: VideoExportService = Depends(get_video_export_service)) -> FileResponse:
    return FileResponse(service.export_file(project_id, export_id, filename), filename=filename)


@router.get("/{project_id}/exports/{export_id}/download")
def download_export_archive(project_id: str, export_id: str, service: VideoExportService = Depends(get_video_export_service)) -> FileResponse:
    """Download a completed export snapshot as one ZIP file."""

    return FileResponse(
        service.export_archive(project_id, export_id),
        media_type="application/zip",
        filename=f"pose-export-{export_id}.zip",
    )


@router.put("/{project_id}/workspace-state")
def save_workspace_state(project_id: str, payload: WorkspaceStatePayload, service: VideoService = Depends(get_video_service)) -> dict[str, Any]:
    return service.save_workspace_state(project_id, payload.model_dump())
