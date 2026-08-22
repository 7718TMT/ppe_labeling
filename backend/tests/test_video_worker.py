from pathlib import Path

from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_feature_service import VideoFeatureService
from backend.app.services.video_service import VideoService
from backend.app.services.video_worker import VideoWorker


def test_persistent_job_claim_progress_and_restart_recovery(tmp_path: Path) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    project = VideoService(repository, storage).create_project("Jobs")
    job = repository.enqueue_job(project["project_id"], "synthetic", priority=42)
    worker = VideoWorker(repository, storage, tmp_path / "pose.pt", VideoFeatureService(repository, storage), extra_handlers={"synthetic": lambda _job, progress: progress(0.8)})
    completed = worker.run_once()
    assert completed and completed["status"] == "completed" and completed["progress"] == 1
    running = repository.enqueue_job(project["project_id"], "orphan")
    repository.update_job(running["job_id"], status="running", worker_id="dead-worker")
    repository.execute("UPDATE processing_jobs SET heartbeat_at='2000-01-01 00:00:00' WHERE job_id=?", (running["job_id"],))
    assert worker.recover() == 1
    assert repository.get_job(running["job_id"])["status"] == "queued"


def test_pause_resume_cancel_retry_and_priority_are_persistent(tmp_path: Path) -> None:
    repository = VideoRepository(tmp_path / "state.sqlite3")
    storage = VideoStorageRepository(tmp_path / "storage")
    service = VideoService(repository, storage)
    project = service.create_project("Controls")
    job = repository.enqueue_job(project["project_id"], "synthetic")
    assert service.control_job(job["job_id"], "pause")["status"] == "paused"
    assert service.control_job(job["job_id"], "resume")["status"] == "queued"
    prioritized = service.control_job(job["job_id"], "prioritize")
    assert prioritized["priority"] >= 1000
    assert service.control_job(job["job_id"], "cancel")["status"] == "cancelled"
    retried = service.control_job(job["job_id"], "retry")
    assert retried["status"] == "queued" and retried["retry_count"] == 1


def test_pipeline_successor_runs_before_another_queued_video(tmp_path: Path) -> None:
    """Keep a video's dependent stages together for prompt readiness."""

    repository = VideoRepository(tmp_path / "state.sqlite3")
    project = VideoService(repository, VideoStorageRepository(tmp_path / "storage")).create_project("Queue")
    first = repository.enqueue_job(project["project_id"], "first", priority=100)
    repository.enqueue_job(project["project_id"], "other", priority=100)

    claimed = repository.claim_job("worker")
    assert claimed and claimed["job_id"] == first["job_id"]
    _completed, successor = repository.complete_job_and_enqueue_next(first["job_id"], "second")

    assert successor and successor["priority"] == 101
    next_claimed = repository.claim_job("worker")
    assert next_claimed and next_claimed["job_id"] == successor["job_id"]
