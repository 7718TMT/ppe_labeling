"""Pydantic HTTP contracts for the separate video-labeling capability."""

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


class JobControl(BaseModel):
    action: Literal["pause", "resume", "cancel", "retry", "prioritize"]


class QueueRequest(BaseModel):
    priority: int = Field(default=100, ge=0, le=10000)


class ProcessRequest(QueueRequest):
    mode: Literal["threshold", "model"]


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


class ProcessingOptionsResponse(BaseModel):
    threshold_available: bool
    model_available: bool
    model_message: str | None = None


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
