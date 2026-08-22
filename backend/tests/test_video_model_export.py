import io
import json
import zipfile
from pathlib import Path

import joblib
import numpy as np
import pytest

from backend.app.domain.errors import VideoValidationError
from backend.app.domain.video import FEATURE_SCHEMA_VERSION, WINDOW_CONFIG_VERSION
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_export_service import VideoExportService
from backend.app.services.video_feature_service import VideoFeatureService
from backend.app.services.video_features import feature_columns
from backend.app.services.video_model_service import VideoModelService
from backend.app.services.video_service import VideoService


class TrustedProbabilityModel:
    classes_ = np.asarray([0, 1, 2])

    def predict_proba(self, matrix):
        return np.tile(np.asarray([[.05, .85, .10]], dtype=np.float32), (len(matrix), 1))


class AlternatingProbabilityModel:
    """Return one isolated raw running result between falling windows."""

    classes_ = np.asarray([0, 1, 2])

    def predict_proba(self, matrix):
        assert len(matrix) == 3
        return np.asarray(
            [
                [.01, .01, .98],
                [.02, .68, .30],
                [.01, .01, .98],
            ],
            dtype=np.float32,
        )


def setup_ready_project(tmp_path: Path):
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    project = VideoService(repository, storage).create_project("Export")
    video = repository.create_video(project["project_id"], {"filename":"ready.mp4","relative_path":"raw/ready.mp4","file_hash":"ready","original_fps":24,"canonical_fps":24,"original_frame_count":60,"canonical_frame_count":60,"duration_seconds":2.5,"width":100,"height":200,"codec":"mp4v","file_size":1,"pose_cache_version":"pose-v1","feature_cache_version":FEATURE_SCHEMA_VERSION,"processing_status":"feature_ready","is_approved":1,"approval_revision":1,"annotation_revision":1,"annotation_status":"approved"})
    repository.replace_tracks(video["video_id"], [{"track_id":1,"start_frame":0,"end_frame":59,"valid_frame_count":60,"gap_count":0,"avg_person_confidence":.9,"avg_keypoint_confidence":.9,"valid_frame_ratio":1,"missing_ankle_ratio":0,"quality_status":"good","include_in_export":1,"exclude_reason":None}])
    repository.execute("INSERT INTO video_segments(segment_id,video_id,track_id,start_frame,end_frame,label,annotation_version) VALUES ('s1',?,1,0,59,'running',1)",(video["video_id"],))
    repository.replace_windows(video["video_id"],[{"track_id":1,"start_frame":0,"end_frame":59,"label":"running","label_reason":"running_ratio","quality_score":.9,"quality_status":"good","include_in_export":1,"exclude_reason":None,"window_config_version":WINDOW_CONFIG_VERSION,"feature_status":"ready","stale":0}])
    window=repository.list_windows(video["video_id"])[0]
    raw={name:.1 for name in feature_columns()}
    feature={"window_id":window["window_id"],"video_id":video["video_id"],"track_id":1,"start_frame":0,"end_frame":59,"label":"running","feature_schema_version":FEATURE_SCHEMA_VERSION,"raw":raw,"transformed":{"running_score":.9},"provenance":{},"quality":{"status":"good","valid_frame_ratio":1}}
    storage.write_json(storage.artifact_path(project["project_id"],"features",video["video_id"],FEATURE_SCHEMA_VERSION),{"feature_schema_version":FEATURE_SCHEMA_VERSION,"windows":[feature]})
    detection={"track_id":1,"bbox":[0,0,100,200],"keypoints":[[1,1]]*17,"keypoint_scores":[.9]*17,"person_confidence":.9}
    storage.write_json(storage.artifact_path(project["project_id"],"pose",video["video_id"],"pose-v1"),{"frames":[{"frame_index":index,"tracks":[detection]} for index in range(60)]})
    return repository,storage,project,video


def model_manifest():
    return {"name":"RF suggestions","version":"1.0","class_map":{"others":0,"running":1,"falling":2},"feature_schema_version":FEATURE_SCHEMA_VERSION,"feature_columns":feature_columns(),"window_length":60,"stride":12,"canonical_fps":24,"inference":{"minimum_probability":.6}}


def test_model_compatibility_reports_exact_mismatches_and_requires_trust(tmp_path: Path) -> None:
    repository,storage,project,_video=setup_ready_project(tmp_path)
    features=VideoFeatureService(repository,storage); service=VideoModelService(repository,storage,features)
    bad={**model_manifest(),"canonical_fps":30,"feature_columns":feature_columns()[::-1]}
    errors=service.compatibility_errors(bad)
    assert any("canonical_fps" in item for item in errors) and any("column order" in item for item in errors)
    artifact_path=tmp_path/"model.joblib";joblib.dump(TrustedProbabilityModel(),artifact_path)
    with pytest.raises(VideoValidationError,match="execute code"):
        service.import_model(project["project_id"],"model.joblib",io.BytesIO(artifact_path.read_bytes()),model_manifest(),False)


def test_trusted_joblib_predictions_and_suggestions_preserve_model_version(tmp_path: Path) -> None:
    repository,storage,project,video=setup_ready_project(tmp_path)
    service=VideoModelService(repository,storage,VideoFeatureService(repository,storage))
    artifact_path=tmp_path/"model.joblib";joblib.dump(TrustedProbabilityModel(),artifact_path)
    model=service.import_model(project["project_id"],"model.joblib",io.BytesIO(artifact_path.read_bytes()),model_manifest(),True)
    assert model["compatibility_status"]=="compatible"
    suggestions=service.run_inference(video["video_id"],model["external_model_id"])
    assert suggestions[0]["suggested_label"]=="running"
    assert repository.list_segments(video["video_id"])[0]["source_type"]=="manual"


def test_behavior_preprocessing_matches_training_notebook() -> None:
    """Keep inference feature order and transforms aligned with the notebook."""

    raw = {name: -4.0 for name in feature_columns()}
    raw.update({
        "ground_speed_mean": 9.0,
        "skeleton_spread_ratio_max": np.e ** (np.e - 1) - 1,
    })
    matrix = VideoModelService._behavior_matrix([{"raw": raw}])
    columns = [
        name for name in feature_columns()
        if name not in {"track_gap_count", "valid_frame_ratio"}
    ]

    assert matrix.shape == (1, 141)
    assert matrix[0, columns.index("ground_speed_mean")] == pytest.approx(3.0)
    assert matrix[0, columns.index("skeleton_spread_ratio_max")] == pytest.approx(1.0)
    assert matrix[0, columns.index("torso_angle_mean")] == pytest.approx(-4.0)


def test_event_smoothing_suppresses_an_isolated_class_flip(tmp_path: Path) -> None:
    """Raw windows remain inspectable while merged events use smoothing."""

    repository, storage, project, video = setup_ready_project(tmp_path)
    repository.replace_windows(
        video["video_id"],
        [
            {
                "track_id": 1,
                "start_frame": start,
                "end_frame": start + 59,
                "label": "others",
                "label_reason": "inference",
                "quality_score": .9,
                "quality_status": "good",
                "include_in_export": 1,
                "exclude_reason": None,
                "window_config_version": WINDOW_CONFIG_VERSION,
                "feature_status": "ready",
                "stale": 0,
            }
            for start in (0, 12, 24)
        ],
    )
    rows = []
    for window in repository.list_windows(video["video_id"]):
        rows.append({
            "window_id": window["window_id"],
            "video_id": video["video_id"],
            "track_id": 1,
            "start_frame": window["start_frame"],
            "end_frame": window["end_frame"],
            "label": "others",
            "feature_schema_version": FEATURE_SCHEMA_VERSION,
            "raw": {name: .1 for name in feature_columns()},
            "transformed": {},
            "provenance": {},
            "quality": {"status": "good", "valid_frame_ratio": 1},
        })
    storage.write_json(
        storage.artifact_path(
            project["project_id"],
            "features",
            video["video_id"],
            FEATURE_SCHEMA_VERSION,
        ),
        {"feature_schema_version": FEATURE_SCHEMA_VERSION, "windows": rows},
    )
    artifact_path = tmp_path / "alternating.joblib"
    joblib.dump(AlternatingProbabilityModel(), artifact_path)
    service = VideoModelService(
        repository,
        storage,
        VideoFeatureService(repository, storage),
    )
    model = service.import_model(
        project["project_id"],
        "alternating.joblib",
        io.BytesIO(artifact_path.read_bytes()),
        model_manifest(),
        True,
    )

    events = service.run_inference(
        video["video_id"], model["external_model_id"]
    )
    predictions = repository.all(
        "SELECT predicted_label FROM model_window_predictions "
        "ORDER BY prediction_id"
    )

    assert sorted(row["predicted_label"] for row in predictions) == [
        "falling", "falling", "running",
    ]
    assert len(events) == 1
    assert events[0]["suggested_label"] == "falling"
    assert events[0]["start_frame"] == 0
    assert events[0]["end_frame"] == 83


def test_atomic_export_contains_training_samples_and_manifest(tmp_path: Path) -> None:
    repository,storage,project,video=setup_ready_project(tmp_path)
    service=VideoExportService(repository,storage,VideoFeatureService(repository,storage))
    assert service.validate(project["project_id"])["errors"]==[]
    export=repository.create_export(project["project_id"])
    progress=[]
    service.run_job({"stage":f"export:{export['export_id']}"},progress.append)
    completed=repository.get_export(export["export_id"])
    directory=Path(completed["artifact_path"])
    expected={"annotations.jsonl","keypoint_windows.npz","manifest.json"}
    assert expected=={path.name for path in directory.iterdir()}
    arrays=np.load(directory/"keypoint_windows.npz")
    assert arrays["keypoints"].shape==(1,60,17,2)
    manifest=json.loads((directory/"manifest.json").read_text())
    assert manifest["class_map"]=={"others":0,"running":1,"falling":2}
    assert manifest["video_hashes"]=={video["video_id"]:"ready"}
    assert not (directory.parent/f".{export['export_id']}.staging").exists()
    archive=service.export_archive(project["project_id"],export["export_id"])
    with zipfile.ZipFile(archive) as output:
        assert expected==set(output.namelist())
