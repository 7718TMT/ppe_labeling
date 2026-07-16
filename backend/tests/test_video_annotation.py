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
    with pytest.raises(VideoValidationError, match="This segment conflicts with another segment"):
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


def test_extend_segment_fills_only_adjacent_gaps(tmp_path: Path) -> None:
    _repository, _storage, service, video = setup_video(tmp_path)
    service.save_segment(video["video_id"], 1, 10, 20, "others", 0)
    target = service.save_segment(video["video_id"], 1, 30, 40, "running", 1)["segment"]
    service.save_segment(video["video_id"], 1, 50, 60, "falling", 2)

    expanded = service.extend_segment(video["video_id"], target["segment_id"], 3)

    assert expanded["segment"]["start_frame"] == 21
    assert expanded["segment"]["end_frame"] == 49


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


def test_track_edit_tolerates_a_missing_or_corrupt_pose_cache(tmp_path: Path) -> None:
    """A manual correction still commits when an old pose file is unreadable."""

    repository, storage, service, video = setup_video(tmp_path)
    project_id = str(repository.get_video(video["video_id"])["project_id"])
    repository.update_video(video["video_id"], pose_cache_version="corrupt-pose")
    pose_path = storage.artifact_path(
        project_id,
        "pose",
        video["video_id"],
        "corrupt-pose",
    )
    storage.write_bytes(pose_path, b"not-a-gzip-pose-artifact")

    merged = service.merge_tracks(video["video_id"], 1, 2)

    assert merged["track_id"] == 1
    assert [track["track_id"] for track in repository.list_tracks(video["video_id"])] == [
        1
    ]
    derivative = repository.active_job_for_video(video["video_id"])
    assert derivative and derivative["stage"] == "annotation_derivatives"


def test_track_merge_switches_to_an_immutable_staged_pose_version(
    tmp_path: Path,
) -> None:
    """A successful merge changes the pose pointer without overwriting history."""

    repository, storage, service, video = setup_video(tmp_path)
    video_id = str(video["video_id"])
    project_id = str(repository.get_video(video_id)["project_id"])
    source_version = "pose-source"
    source_path = storage.artifact_path(
        project_id,
        "pose",
        video_id,
        source_version,
    )
    storage.write_json(
        source_path,
        {
            "frames": [
                {
                    "frame_index": 0,
                    "tracks": [{"track_id": 2}],
                }
            ]
        },
    )
    repository.update_video(video_id, pose_cache_version=source_version)

    service.merge_tracks(video_id, 1, 2)

    staged_version = str(repository.get_video(video_id)["pose_cache_version"])
    assert staged_version != source_version
    assert storage.read_json(source_path)["frames"][0]["tracks"][0]["track_id"] == 2
    staged_path = storage.artifact_path(
        project_id,
        "pose",
        video_id,
        staged_version,
    )
    assert storage.read_json(staged_path)["frames"][0]["tracks"][0]["track_id"] == 1


def test_failed_track_merge_keeps_the_previous_pose_pointer_authoritative(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A pre-commit crash leaves only an unreferenced staged pose artifact."""

    repository, storage, service, video = setup_video(tmp_path)
    video_id = str(video["video_id"])
    project_id = str(repository.get_video(video_id)["project_id"])
    source_version = "pose-source"
    source_path = storage.artifact_path(
        project_id,
        "pose",
        video_id,
        source_version,
    )
    storage.write_json(
        source_path,
        {
            "frames": [
                {
                    "frame_index": 0,
                    "tracks": [{"track_id": 2}],
                }
            ]
        },
    )
    repository.update_video(video_id, pose_cache_version=source_version)

    def fail_track_event(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("synthetic database finalization failure")

    monkeypatch.setattr(repository, "_emit_tracks_changed", fail_track_event)
    with pytest.raises(RuntimeError, match="synthetic database finalization failure"):
        service.merge_tracks(video_id, 1, 2)

    assert repository.get_video(video_id)["pose_cache_version"] == source_version
    assert [track["track_id"] for track in repository.list_tracks(video_id)] == [1, 2]
    assert storage.read_json(source_path)["frames"][0]["tracks"][0]["track_id"] == 2
    staged_paths = [
        path
        for path in source_path.parent.glob(f"{video_id}.*.json.gz")
        if path != source_path
    ]
    assert len(staged_paths) == 1
    assert storage.read_json(staged_paths[0])["frames"][0]["tracks"][0]["track_id"] == 1


def test_track_merge_rejects_a_staged_pose_pointer_replaced_by_another_edit(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Two interleaved pose edits cannot silently overwrite one another."""

    repository, storage, service, video = setup_video(tmp_path)
    video_id = str(video["video_id"])
    project_id = str(repository.get_video(video_id)["project_id"])
    source_version = "pose-source"
    source_path = storage.artifact_path(
        project_id,
        "pose",
        video_id,
        source_version,
    )
    storage.write_json(
        source_path,
        {
            "frames": [
                {
                    "frame_index": 0,
                    "tracks": [{"track_id": 2}],
                }
            ]
        },
    )
    repository.update_video(video_id, pose_cache_version=source_version)
    concurrent_version = "pose-concurrent-edit"
    storage.write_json(
        storage.artifact_path(
            project_id,
            "pose",
            video_id,
            concurrent_version,
        ),
        {
            "frames": [
                {
                    "frame_index": 0,
                    "tracks": [{"track_id": 2}],
                }
            ]
        },
    )
    original_merge = repository.merge_tracks_atomically

    def interleave_pointer_change(*args: object, **kwargs: object) -> dict[str, object]:
        repository.update_video(video_id, pose_cache_version=concurrent_version)
        return original_merge(*args, **kwargs)

    monkeypatch.setattr(repository, "merge_tracks_atomically", interleave_pointer_change)
    with pytest.raises(RevisionConflictError, match="Pose data changed"):
        service.merge_tracks(video_id, 1, 2)

    assert repository.get_video(video_id)["pose_cache_version"] == concurrent_version
    assert [track["track_id"] for track in repository.list_tracks(video_id)] == [1, 2]
    assert storage.read_json(source_path)["frames"][0]["tracks"][0]["track_id"] == 2
