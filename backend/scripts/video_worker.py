"""Run the persistent local pose-video job worker."""

from __future__ import annotations

import argparse
from multiprocessing import Process

from backend.app.core.config import get_settings
from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_export_service import VideoExportService
from backend.app.services.video_feature_service import VideoFeatureService
from backend.app.services.video_model_service import VideoModelService
from backend.app.services.video_worker import VideoWorker


def build_worker(worker_suffix: str = "0") -> VideoWorker:
    settings = get_settings()
    repository = VideoRepository(settings.database_path)
    storage = VideoStorageRepository(settings.video_storage_root)
    features = VideoFeatureService(repository, storage)
    models = VideoModelService(repository, storage, features)
    exports = VideoExportService(repository, storage, features)

    def model_handler(job, progress):
        progress(0.05)
        model_id = job.get("external_model_id")
        if not model_id:
            raise ValueError("Model processing job is missing its pinned model ID")
        models.run_inference(job["video_id"], model_id)
        progress(0.95)

    return VideoWorker(
        repository,
        storage,
        settings.pose_model_path,
        features,
        worker_id=f"local-worker-{worker_suffix}",
        extra_handlers={"model": model_handler, "export:*": exports.run_job},
    )


def run_forever(worker_suffix: str) -> None:
    build_worker(worker_suffix).run_forever()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--once", action="store_true", help="Process at most one queued job and exit")
    parser.add_argument("--concurrency", type=int, help="Override VIDEO_WORKER_CONCURRENCY")
    args = parser.parse_args()
    settings = get_settings()
    concurrency = args.concurrency or settings.video_worker_concurrency
    if concurrency < 1:
        parser.error("concurrency must be at least one")
    worker = build_worker("0")
    worker.recover()
    if args.once:
        worker.run_once()
    elif concurrency == 1:
        worker.run_forever()
    else:
        processes = [Process(target=run_forever, args=(str(index),), daemon=False) for index in range(concurrency)]
        for process in processes:
            process.start()
        for process in processes:
            process.join()


if __name__ == "__main__":
    main()
