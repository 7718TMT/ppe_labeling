"""Worker-track and segment annotation request contracts."""

from backend.app.api.schemas.video.contracts import (
    InclusionPayload, ReassignPayload, RevisionPayload, SegmentInclusionPayload,
    SegmentMergePayload, SegmentSplitPayload, SegmentWrite,
    TrackMergeMultiplePayload, TrackMergePayload, TrackSplitPayload,
)

__all__ = [
    "InclusionPayload", "ReassignPayload", "RevisionPayload",
    "SegmentInclusionPayload", "SegmentMergePayload", "SegmentSplitPayload",
    "SegmentWrite", "TrackMergeMultiplePayload", "TrackMergePayload",
    "TrackSplitPayload",
]
