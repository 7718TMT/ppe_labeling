"""Compatibility module for video-labeling HTTP contracts.

New code imports the cohesive modules in this package; this module remains the
single implementation source during the staged API-package migration.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    config: dict[str, Any] | None = None


class ProjectConfigUpdate(BaseModel):
    config: dict[str, Any]


class VideoDeleteResponse(BaseModel):
    video_id: str
    filename: str
    deleted: bool
    owned_copy_removed: bool


class VideoRenamePayload(BaseModel):
    """User-selected basename used for a project-wide video rename."""

    prefix: str = Field(min_length=1, max_length=80)


class VideoTrimPayload(BaseModel):
    """Inclusive canonical-frame range and destination for a video trim."""

    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)
    save_mode: Literal["replace", "copy"]
    filename: str | None = Field(default=None, max_length=255)
    suggestion_mode: Literal["threshold", "model"] = "threshold"


class JobControl(BaseModel):
    action: Literal["pause", "resume", "cancel", "retry", "prioritize"]


class QueueRequest(BaseModel):
    priority: int = Field(default=100, ge=0, le=10000)


class ProcessRequest(QueueRequest):
    mode: Literal["threshold", "model"]
    overwrite_labels: bool = False


class ProcessingJobResponse(BaseModel):
    job_id: str
    project_id: str
    video_id: str | None = None
    stage: str
    status: str
    priority: int
    progress: float
    target_mode: Literal["threshold", "model"] = "threshold"
    external_model_id: str | None = None
    error_message: str | None = None


class AnnotationDerivativeRefreshResponse(BaseModel):
    """Result of requesting label-derived windows/features to be rebuilt."""

    requested_revision: int = Field(ge=0)
    status: Literal["queued", "deferred", "already_queued"]
    job: ProcessingJobResponse | None = None


class ProcessingOptionsResponse(BaseModel):
    threshold_available: bool
    model_available: bool
    model_message: str | None = None


class WorkspaceEventResponse(BaseModel):
    """One durable workspace event delivered by delta polling or SSE."""

    event_id: int = Field(ge=1)
    project_id: str
    video_id: str | None = None
    event_type: str
    payload: dict[str, Any]
    created_at: str


class WorkspaceChangesResponse(BaseModel):
    """A bounded cursor-based event delta for workspace reconnection."""

    events: list[WorkspaceEventResponse]
    last_event_id: int = Field(ge=0)
    resync_required: bool = False
    has_more: bool = False


class WorkspaceSnapshotResponse(BaseModel):
    """The initial compact state read for one video-labeling workspace."""

    project: dict[str, Any]
    videos: list[dict[str, Any]]
    jobs: list[dict[str, Any]]
    processing_options: ProcessingOptionsResponse
    exports: list[dict[str, Any]] = Field(default_factory=list)
    last_event_id: int = Field(ge=0)


class InclusionPayload(BaseModel):
    include: bool
    reason: str | None = None


class SegmentInclusionPayload(InclusionPayload):
    expected_revision: int = Field(ge=0)


class SegmentWrite(BaseModel):
    track_id: int = Field(ge=0)
    start_frame: int = Field(ge=0)
    end_frame: int = Field(ge=0)
    label: Literal["others", "running", "falling"]
    expected_revision: int = Field(ge=0)


class RevisionPayload(BaseModel):
    expected_revision: int = Field(ge=0)


class SegmentSplitPayload(RevisionPayload):
    frame: int = Field(ge=0)


class SegmentMergePayload(RevisionPayload):
    segment_ids: list[str] = Field(min_length=2)


class TrackMergePayload(BaseModel):
    source_track_id: int = Field(ge=0)


class TrackMergeMultiplePayload(BaseModel):
    """Payload for merging multiple tracks into the first one in the list."""

    track_ids: list[int] = Field(min_length=2)


class TrackSplitPayload(BaseModel):
    frame: int = Field(ge=0)


class ReassignPayload(RevisionPayload):
    target_track_id: int = Field(ge=0)


class ThresholdProfilePayload(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    config: dict[str, Any]
    profile_id: str | None = None


class WorkspaceStatePayload(BaseModel):
    video_id: str | None = None
    track_id: int | None = None
    frame_index: int = Field(default=0, ge=0)
    suggestion_source: Literal["Off", "Threshold", "AI"] = "Threshold"


class WindowReviewPayload(BaseModel):
    include: bool
    reason: str | None = None
