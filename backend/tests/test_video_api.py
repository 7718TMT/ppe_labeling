import io
import zipfile
from pathlib import Path

import cv2
import numpy as np
import pytest
from fastapi.testclient import TestClient

from backend.app.api.dependencies import get_video_annotation_service, get_video_export_service, get_video_feature_service, get_video_model_service, get_video_service
from backend.app.main import create_app
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_annotation_service import VideoAnnotationService
from backend.app.services.video_export_service import VideoExportService
from backend.app.services.video_feature_service import VideoFeatureService
from backend.app.services.video_model_service import VideoModelService
from backend.app.services.video_service import VideoService


@pytest.fixture
def video_api(tmp_path: Path):
    repository=VideoRepository(tmp_path/"state.sqlite3");storage=VideoStorageRepository(tmp_path/"storage")
    feature=VideoFeatureService(repository,storage)
    services={get_video_service:VideoService(repository,storage),get_video_annotation_service:VideoAnnotationService(repository,storage),get_video_feature_service:feature,get_video_model_service:VideoModelService(repository,storage,feature),get_video_export_service:VideoExportService(repository,storage,feature)}
    app=create_app()
    for dependency,value in services.items():app.dependency_overrides[dependency]=lambda value=value:value
    with TestClient(app) as client:yield client,repository,storage


def video_bytes(tmp_path: Path) -> bytes:
    path=tmp_path/"api.mp4";writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*"mp4v"),24,(32,24))
    for index in range(60):writer.write(np.full((24,32,3),index,dtype=np.uint8))
    writer.release();return path.read_bytes()


def test_project_import_queue_and_optimistic_annotation_api(video_api, tmp_path: Path) -> None:
    """Test the full import-to-annotation API flow.

    After import the pipeline is auto-queued (#7), so we check that
    at least one job exists before manually requesting processing.
    """
    client, repository, _storage = video_api
    project = client.post("/api/v1/video-projects", json={"name": "API Workflow"}).json()
    project_id = project["project_id"]
    response = client.post(
        f"/api/v1/video-projects/{project_id}/videos/import",
        files=[("files", ("fixture.mp4", video_bytes(tmp_path), "video/mp4"))],
    )
    assert response.status_code == 200
    video = response.json()[0]
    video_id = video["video_id"]
    # After import the pipeline is auto-queued (mode defaults to threshold, #7)
    auto_jobs = client.get(f"/api/v1/video-projects/{project_id}/jobs").json()
    assert len(auto_jobs) >= 1 and auto_jobs[0]["status"] == "queued"
    processed = client.post(
        f"/api/v1/video-projects/{project_id}/videos/{video_id}/process",
        json={"mode": "threshold", "priority": 1000},
    )
    assert processed.status_code == 200
    jobs = processed.json()
    # Returns the already-queued job since it hasn't completed yet
    assert jobs[0]["stage"] in {"canonicalize", "pose_track", "features", "threshold"}
    assert jobs[0]["status"] == "queued"
    repeated = client.post(
        f"/api/v1/video-projects/{project_id}/videos/{video_id}/process",
        json={"mode": "threshold", "priority": 1000},
    )
    assert repeated.json()[0]["job_id"] == jobs[0]["job_id"]
    options=client.get(
        f"/api/v1/video-projects/{project_id}/processing-options"
    ).json()
    assert options=={
        "threshold_available":True,
        "model_available":False,
        "model_message":"Model suggestions are not configured for this project.",
    }
    unavailable=client.post(
        f"/api/v1/video-projects/{project_id}/videos/{video_id}/process",
        json={"mode":"model","priority":1000},
    )
    assert unavailable.status_code==422
    assert unavailable.json()=={
        "detail":"Model suggestions are not configured for this project."
    }
    repository.replace_tracks(video_id,[{"track_id":1,"start_frame":0,"end_frame":59,"valid_frame_count":60,"gap_count":0,"avg_person_confidence":.9,"avg_keypoint_confidence":.9,"valid_frame_ratio":1,"missing_ankle_ratio":0,"quality_status":"good","include_in_export":1,"exclude_reason":None}])
    created=client.post(f"/api/v1/video-projects/{project_id}/videos/{video_id}/segments",json={"track_id":1,"start_frame":0,"end_frame":20,"label":"others","expected_revision":0})
    assert created.status_code==200 and created.json()["revision"]==1
    conflict=client.post(f"/api/v1/video-projects/{project_id}/videos/{video_id}/segments",json={"track_id":1,"start_frame":21,"end_frame":30,"label":"running","expected_revision":0})
    assert conflict.status_code==409 and "current 1" in conflict.json()["detail"]
    history=client.get(f"/api/v1/video-projects/{project_id}/videos/{video_id}/history").json()
    assert history[0]["operation"]=="create"
    assert client.post(f"/api/v1/video-projects/{project_id}/videos/{video_id}/approve").status_code==200
    assert set(client.get(f"/api/v1/video-projects/{project_id}/videos/{video_id}/validate").json())=={"valid","errors"}


def test_real_endpoint_workflow_windows_features_suggestions_and_export_validation(video_api)->None:
    client,repository,storage=video_api
    project=client.post("/api/v1/video-projects",json={"name":"End to End"}).json();project_id=project["project_id"]
    video=repository.create_video(project_id,{"filename":"synthetic.mp4","relative_path":"raw/synthetic.mp4","file_hash":"e2e","original_fps":24,"canonical_fps":24,"original_frame_count":60,"canonical_frame_count":60,"duration_seconds":2.5,"width":100,"height":200,"codec":"mp4v","file_size":1,"pose_cache_version":"pose-v1","processing_status":"annotation_ready"})
    video_id=video["video_id"]
    repository.replace_tracks(video_id,[{"track_id":1,"start_frame":0,"end_frame":59,"valid_frame_count":60,"gap_count":0,"avg_person_confidence":.9,"avg_keypoint_confidence":.9,"valid_frame_ratio":1,"missing_ankle_ratio":0,"quality_status":"good","include_in_export":1,"exclude_reason":None}])
    points=[[50,80] for _ in range(17)];points[0]=[50,20];points[5]=[40,40];points[6]=[60,40];points[11]=[45,100];points[12]=[55,100];points[15]=[45,190];points[16]=[55,190]
    detection={"track_id":1,"bbox":[0,0,100,200],"keypoints":points,"keypoint_scores":[.9]*17,"person_confidence":.9}
    storage.write_json(storage.artifact_path(project_id,"pose",video_id,"pose-v1"),{"frames":[{"frame_index":index,"tracks":[detection]} for index in range(60)]})
    assert client.post(f"/api/v1/video-projects/{project_id}/videos/{video_id}/segments",json={"track_id":1,"start_frame":0,"end_frame":59,"label":"others","expected_revision":0}).status_code==200
    windows=client.post(f"/api/v1/video-projects/{project_id}/videos/{video_id}/windows/generate").json();assert windows[0]["label"]=="others"
    generated=client.post(f"/api/v1/video-projects/{project_id}/videos/{video_id}/features/generate");assert generated.status_code==200 and generated.json()["windows"]
    assert client.post(f"/api/v1/video-projects/{project_id}/videos/{video_id}/approve").status_code==200
    validation=client.get(f"/api/v1/video-projects/{project_id}/exports/validate").json();assert validation["errors"]==[]
    queued=client.post(f"/api/v1/video-projects/{project_id}/exports").json();assert queued["queued"] is True
    export_id=queued["export"]["export_id"]
    VideoExportService(repository,storage,VideoFeatureService(repository,storage)).run_job(
        {"stage":f"export:{export_id}"},lambda _progress:None,
    )
    archive=client.get(f"/api/v1/video-projects/{project_id}/exports/{export_id}/download")
    assert archive.status_code==200 and archive.headers["content-type"]=="application/zip"
    with zipfile.ZipFile(io.BytesIO(archive.content)) as output:
        assert "manifest.json" in output.namelist()
