from pathlib import Path

import pytest

from backend.app.domain.errors import RevisionConflictError, VideoValidationError
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_annotation_service import VideoAnnotationService
from backend.app.services.video_service import VideoService


def setup_video(tmp_path: Path):
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    project = VideoService(repository, storage).create_project("Annotations")
    video = repository.create_video(project["project_id"], {
        "filename":"fixture.mp4","relative_path":"raw/fixture.mp4","file_hash":"abc",
        "original_fps":24,"canonical_fps":24,"original_frame_count":120,"canonical_frame_count":120,
        "duration_seconds":5,"width":640,"height":480,"codec":"mp4v","file_size":1,
    })
    repository.replace_tracks(video["video_id"], [{
        "track_id":1,"start_frame":0,"end_frame":119,"valid_frame_count":120,"gap_count":0,
        "avg_person_confidence":.9,"avg_keypoint_confidence":.8,"valid_frame_ratio":1,
        "missing_ankle_ratio":0,"quality_status":"good","include_in_export":1,"exclude_reason":None,
    },{
        "track_id":2,"start_frame":20,"end_frame":100,"valid_frame_count":81,"gap_count":0,
        "avg_person_confidence":.8,"avg_keypoint_confidence":.7,"valid_frame_ratio":1,
        "missing_ankle_ratio":0,"quality_status":"good","include_in_export":1,"exclude_reason":None,
    }])
    return repository, storage, VideoAnnotationService(repository, storage), video


def test_segment_validation_overlap_revision_history_and_approval(tmp_path: Path) -> None:
    repository, _storage, service, video = setup_video(tmp_path)
    created = service.save_segment(video["video_id"], 1, 0, 30, "others", 0)
    assert created["revision"] == 1
    with pytest.raises(VideoValidationError, match="conflicts"):
        service.save_segment(video["video_id"], 1, 20, 40, "running", 1)
    service.save_segment(video["video_id"], 2, 20, 40, "running", 1)
    with pytest.raises(RevisionConflictError):
        service.save_segment(video["video_id"], 1, 31, 50, "falling", 1)
    approved = service.approve(video["video_id"])
    assert approved["is_approved"] == 1 and approved["approval_revision"] == 2
    updated = service.save_segment(video["video_id"], 1, 0, 29, "others", 2, created["segment"]["segment_id"])
    assert repository.get_video(video["video_id"])["is_approved"] == 0
    assert len(repository.list_history(video["video_id"])) == 3
    assert updated["revision"] == 3


def test_undo_redo_and_track_edits_preserve_labels_as_labeled(tmp_path: Path) -> None:
    repository, _storage, service, video = setup_video(tmp_path)
    segment = service.save_segment(video["video_id"], 1, 10, 15, "falling", 0)["segment"]
    assert service.undo(video["video_id"], 1) == 2
    assert repository.list_segments(video["video_id"]) == []
    assert service.redo(video["video_id"], 2) == 3
    assert repository.list_segments(video["video_id"])[0]["segment_id"] == segment["segment_id"]
    service.merge_tracks(video["video_id"], 2, 1)
    preserved = repository.list_segments(video["video_id"])[0]
    assert preserved["track_id"] == 2
    assert repository.get_video(video["video_id"])["annotation_status"] == "labeled"


def test_invalid_class_bounds_and_track_exclusion(tmp_path: Path) -> None:
    _repository, _storage, service, video = setup_video(tmp_path)
    with pytest.raises(VideoValidationError, match="Human label"):
        service.save_segment(video["video_id"], 1, 0, 10, "walking", 0)
    with pytest.raises(VideoValidationError, match="track lifespan"):
        service.save_segment(video["video_id"], 2, 0, 10, "others", 0)
    excluded = service.set_track_inclusion(video["video_id"], 1, False, "wrong_track")
    assert excluded["include_in_export"] == 0 and excluded["exclude_reason"] == "wrong_track"
