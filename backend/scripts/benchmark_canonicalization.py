"""Measure the canonical-video stage without running pose or inference.

Example:
    uv run python -m backend.scripts.benchmark_canonicalization path/to/video.mp4
"""

from __future__ import annotations

import argparse
import json
import tempfile
import time
from pathlib import Path

from backend.app.repositories.video_db import VideoRepository
from backend.app.repositories.video_storage import VideoStorageRepository
from backend.app.services.video_feature_service import VideoFeatureService
from backend.app.services.video_service import VideoService
from backend.app.services.video_worker import VideoWorker


def benchmark(video_path: Path) -> dict[str, float | int | str]:
    """Run only canonicalization in disposable storage and return its metrics."""

    with tempfile.TemporaryDirectory(prefix="ppe-labeling-canonical-") as directory:
        root = Path(directory)
        repository = VideoRepository(root / "state.sqlite3")
        storage = VideoStorageRepository(root / "storage")
        service = VideoService(repository, storage)
        project = service.create_project("Canonical benchmark")
        with video_path.open("rb") as source:
            video = service.import_video(project["project_id"], video_path.name, source)
        worker = VideoWorker(
            repository,
            storage,
            root / "unused-pose.pt",
            VideoFeatureService(repository, storage),
            inference_device="cpu",
        )

        started = time.perf_counter()
        worker._canonicalize(
            {
                "job_id": "canonical-benchmark",
                "project_id": project["project_id"],
                "video_id": video["video_id"],
            },
            lambda _progress: None,
        )
        elapsed = time.perf_counter() - started
        frames = int(video["canonical_frame_count"])
        return {
            "source": str(video_path),
            "width": int(video["width"]),
            "height": int(video["height"]),
            "source_fps": float(video["original_fps"]),
            "canonical_frames": frames,
            "elapsed_seconds": round(elapsed, 3),
            "frames_per_second": round(frames / elapsed, 3) if elapsed else 0.0,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("video", type=Path, help="Existing source video to benchmark")
    args = parser.parse_args()
    path = args.video.resolve()
    if not path.is_file():
        parser.error(f"Video does not exist: {path}")
    print(json.dumps(benchmark(path), indent=2))


if __name__ == "__main__":
    main()
