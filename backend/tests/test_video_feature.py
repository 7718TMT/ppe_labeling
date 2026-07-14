from pathlib import Path

import pytest

from backend.app.domain.video import FEATURE_SCHEMA_VERSION, WINDOW_CONFIG_VERSION, threshold_profile_config
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_annotation_service import VideoAnnotationService
from backend.app.services.video_feature_service import VideoFeatureService
from backend.app.services.video_features import extract_window_features, ramp, transform_features
from backend.app.services.video_service import VideoService


def pose_frame(frame_index: int, x_offset: float = 0) -> dict:
    points = [[50 + x_offset, 80] for _ in range(17)]
    points[0] = [50 + x_offset, 20]
    points[5], points[6] = [40 + x_offset, 40], [60 + x_offset, 40]
    points[11], points[12] = [45 + x_offset, 100], [55 + x_offset, 100]
    points[15], points[16] = [45 + x_offset, 190], [55 + x_offset, 190]
    return {"track_id": 1, "bbox": [x_offset, 0, 100 + x_offset, 200], "keypoints": points, "keypoint_scores": [.9] * 17, "person_confidence": .95, "frame_index": frame_index}


def test_groups_a_to_e_are_deterministic_and_provenance_is_retained() -> None:
    frames = [pose_frame(index, index * .5) for index in range(60)]
    first = extract_window_features(frames)
    second = extract_window_features(frames)
    assert first == second
    raw = first["raw"]
    assert raw["torso_angle_mean"] == pytest.approx(90)
    assert raw["head_hip_compression_mean"] == pytest.approx(.4)
    assert raw["avg_keypoint_confidence"] == pytest.approx(.9)
    assert raw["missing_ankle_ratio"] == 0
    assert len([name for name in raw if name.startswith("step_")]) == 120
    assert first["provenance"]["step_torso_angle_t0"] == "observed"
    assert first["provenance"]["step_ground_speed_t0"] == "missing"
    assert set(first["provenance"].values()) == {"observed", "missing"}


def test_short_gaps_interpolate_but_long_gaps_remain_missing() -> None:
    frames = [pose_frame(index) for index in range(60)]
    for index in range(20, 23):
        frames[index] = None
    interpolated = extract_window_features(frames, max_interpolation_gap=6)
    assert interpolated["provenance"]["step_torso_angle_t5"] == "interpolated"
    for index in range(20, 31):
        frames[index] = None
    missing = extract_window_features(frames, max_interpolation_gap=6)
    assert missing["provenance"]["step_torso_angle_t5"] == "missing"


def test_transformed_scores_are_clamped_and_fall_inhibits_running() -> None:
    raw = extract_window_features([pose_frame(index) for index in range(60)])["raw"]
    scores = transform_features(raw, threshold_profile_config())
    assert all(0 <= value <= 1 for value in scores.values())
    assert ramp(-10, 0, 1) == 0 and ramp(10, 0, 1) == 1
    assert scores["fall_inhibition_score"] == max(scores["torso_horizontal_score"], scores["final_lying_score_norm"], scores["spread_score"])


def setup_feature_video(tmp_path: Path):
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    project = VideoService(repository, storage).create_project("Features")
    video = repository.create_video(project["project_id"], {"filename":"v.mp4","relative_path":"raw/v.mp4","file_hash":"features","original_fps":24,"canonical_fps":24,"original_frame_count":120,"canonical_frame_count":120,"duration_seconds":5,"width":100,"height":200,"codec":"mp4v","file_size":1,"pose_cache_version":"pose-v1"})
    repository.replace_tracks(video["video_id"], [{"track_id":1,"start_frame":0,"end_frame":119,"valid_frame_count":120,"gap_count":0,"avg_person_confidence":.9,"avg_keypoint_confidence":.9,"valid_frame_ratio":1,"missing_ankle_ratio":0,"quality_status":"good","include_in_export":1,"exclude_reason":None}])
    frames = [{"frame_index":index,"tracks":[{key:value for key,value in pose_frame(index,index*.2).items() if key!="frame_index"}]} for index in range(120)]
    storage.write_json(storage.artifact_path(project["project_id"],"pose",video["video_id"],"pose-v1"),{"frames":frames})
    return repository, storage, project, video


def test_window_mapping_priority_quality_and_unresolved_no_fourth_label(tmp_path: Path) -> None:
    repository, storage, _project, video = setup_feature_video(tmp_path)
    annotations = VideoAnnotationService(repository, storage)
    annotations.save_segment(video["video_id"],1,0,59,"others",0)
    annotations.save_segment(video["video_id"],1,60,89,"running",1)
    annotations.save_segment(video["video_id"],1,90,119,"falling",2)
    windows = VideoFeatureService(repository, storage).generate_windows(video["video_id"])
    assert [(row["start_frame"],row["end_frame"]) for row in windows] == [(0,59),(12,71),(24,83),(36,95),(48,107),(60,119)]
    assert windows[-1]["label"] == "falling"
    assert all(row["label"] in {None,"others","running","falling"} for row in windows)
    assert all(row["window_config_version"] == WINDOW_CONFIG_VERSION for row in windows)


def test_feature_cache_and_threshold_suggestions_are_separate_from_annotations(tmp_path: Path) -> None:
    repository, storage, project, video = setup_feature_video(tmp_path)
    service = VideoFeatureService(repository, storage)
    service.generate_windows(video["video_id"])
    artifact = service.extract_features(video["video_id"])
    assert artifact["feature_schema_version"] == FEATURE_SCHEMA_VERSION
    assert artifact["windows"] and "transformed" in artifact["windows"][0]
    before = repository.list_segments(video["video_id"])
    service.generate_threshold_suggestions(video["video_id"])
    assert repository.list_segments(video["video_id"]) == before
    assert repository.get_project(project["project_id"])["active_threshold_profile_id"]


def test_pending_suggestions_become_editable_ground_truth_once(tmp_path: Path) -> None:
    repository, storage, project, video = setup_feature_video(tmp_path)
    profile_id = project["active_threshold_profile_id"]
    repository.replace_threshold_suggestions(
        video["video_id"],
        profile_id,
        [{
            "track_id": 1, "start_frame": 12, "end_frame": 48,
            "suggested_label": "running", "confidence": 0.91,
            "triggered_conditions_json": "[\"sustained_running_score\"]",
            "supporting_features_json": "{}", "quality_status": "good",
            "review_status": "pending", "artifact_key": "running-12-48",
        }],
    )

    created = VideoAnnotationService(repository, storage).materialize_suggestions(
        video["video_id"], "threshold"
    )

    assert len(created) == 3
    segments = repository.list_segments(video["video_id"])
    assert [(item["start_frame"], item["end_frame"], item["label"]) for item in segments] == [
        (0, 11, "others"), (12, 48, "running"), (49, 119, "others"),
    ]
    assert segments[1]["source_type"] == "threshold"
    assert segments[1]["source_id"]
    assert segments[0]["source_type"] == "auto_default"
    assert repository.get_video(video["video_id"])["annotation_status"] == "labeled"
    assert repository.list_suggestions("threshold_suggestions", video["video_id"])[0]["review_status"] == "accepted"
    assert VideoAnnotationService(repository, storage).materialize_suggestions(video["video_id"], "threshold") == []


def test_tracks_receive_an_others_segment_when_no_suggestions_are_generated(tmp_path: Path) -> None:
    repository, storage, _project, video = setup_feature_video(tmp_path)

    created = VideoAnnotationService(repository, storage).materialize_suggestions(
        video["video_id"], "threshold"
    )

    assert [(item["start_frame"], item["end_frame"], item["label"]) for item in created] == [
        (0, 119, "others"),
    ]
    assert repository.get_video(video["video_id"])["annotation_status"] == "labeled"
