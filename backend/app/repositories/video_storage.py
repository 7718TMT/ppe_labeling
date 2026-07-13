"""Versioned filesystem storage for large video-labeling artifacts."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from backend.app.domain.errors import VideoResourceNotFoundError, VideoValidationError


VIDEO_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}

# Only these directories contain files owned by one imported video. Project-wide
# model packages and immutable export snapshots are intentionally excluded.
VIDEO_SCOPED_DIRECTORIES = (
    "raw",
    "canonical",
    "pose",
    "tracks",
    "features",
    "suggestions",
    "model_predictions",
    "thumbnails",
    "overlays",
)


class VideoStorageRepository:
    """Persist raw videos and replaceable caches below one configured root."""

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def project_dir(self, project_id: str) -> Path:
        return self._within(self.root / project_id)

    def ensure_project(self, project_id: str) -> Path:
        project = self.project_dir(project_id)
        for name in (*VIDEO_SCOPED_DIRECTORIES, "models", "exports"):
            (project / name).mkdir(parents=True, exist_ok=True)
        return project

    def save_raw(self, project_id: str, video_id: str, filename: str, source: BinaryIO) -> tuple[Path, str, int]:
        suffix = Path(filename).suffix.lower()
        if suffix not in VIDEO_EXTENSIONS:
            raise VideoValidationError(f"Unsupported video type: {suffix or 'missing extension'}")
        directory = self.ensure_project(project_id) / "raw"
        target = self._within(directory / f"{video_id}{suffix}")
        digest = hashlib.sha256()
        size = 0
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{video_id}-", suffix=".upload", dir=directory)
        try:
            with os.fdopen(descriptor, "wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_name, target)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise
        return target, digest.hexdigest(), size

    def delete_raw(self, path: Path) -> None:
        self._within(path).unlink(missing_ok=True)

    def raw_path(self, project_id: str, relative_path: str) -> Path:
        project = self.project_dir(project_id)
        path = self._within(project / relative_path)
        try:
            path.relative_to(project)
        except ValueError as exc:
            raise VideoValidationError("Raw video path escapes its project") from exc
        if not path.is_file():
            raise VideoResourceNotFoundError("Raw video file not found")
        return path

    def canonical_path(self, project_id: str, video_id: str) -> Path:
        return self._within(self.ensure_project(project_id) / "canonical" / f"{video_id}.mp4")

    def thumbnail_path(self, project_id: str, video_id: str, fallback: bool = False) -> Path:
        """Return the managed cache path for a video thumbnail."""

        marker = ".placeholder" if fallback else ""
        return self._within(
            self.ensure_project(project_id) / "thumbnails" / f"{video_id}{marker}.jpg"
        )

    def existing_thumbnail(self, project_id: str, video_id: str) -> tuple[Path, bool] | None:
        """Return a cached generated or fallback preview without regenerating it."""

        generated = self.thumbnail_path(project_id, video_id)
        if generated.is_file():
            return generated, False
        fallback = self.thumbnail_path(project_id, video_id, fallback=True)
        if fallback.is_file():
            return fallback, True
        return None

    def artifact_path(self, project_id: str, category: str, video_id: str, version: str, suffix: str = ".json.gz") -> Path:
        if category not in {"pose", "features"}:
            raise ValueError("Unsupported artifact category")
        safe_version = "".join(character for character in version if character.isalnum() or character in "-_.")
        return self._within(self.ensure_project(project_id) / category / f"{video_id}.{safe_version}{suffix}")

    def write_json(self, path: Path, value: Any, compress: bool | None = None) -> None:
        target = self._within(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        use_gzip = target.suffix == ".gz" if compress is None else compress
        temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
        try:
            if use_gzip:
                with gzip.open(temporary, "wt", encoding="utf-8") as output:
                    json.dump(value, output, separators=(",", ":"), allow_nan=False)
            else:
                temporary.write_text(json.dumps(value, separators=(",", ":"), allow_nan=False), encoding="utf-8")
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def write_bytes(self, path: Path, value: bytes) -> None:
        """Atomically publish a binary cache file below the storage root."""

        target = self._within(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        try:
            with os.fdopen(descriptor, "wb") as output:
                output.write(value)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_name, target)
        finally:
            Path(temporary_name).unlink(missing_ok=True)

    def read_json(self, path: Path) -> Any:
        source = self._within(path)
        if not source.is_file():
            raise VideoResourceNotFoundError(f"Artifact not found: {source.name}")
        if source.suffix == ".gz":
            with gzip.open(source, "rt", encoding="utf-8") as input_file:
                return json.load(input_file)
        return json.loads(source.read_text(encoding="utf-8"))

    def copy_model_artifact(
        self, project_id: str, model_id: str, filename: str, source: BinaryIO
    ) -> tuple[Path, str]:
        suffix = Path(filename).suffix.lower()
        if suffix not in {".joblib", ".pkl", ".pickle", ".onnx"}:
            raise VideoValidationError("Model artifact must be joblib, pickle, or ONNX")
        target = self._within(self.ensure_project(project_id) / "models" / f"{model_id}{suffix}")
        digest = hashlib.sha256()
        descriptor, temporary_name = tempfile.mkstemp(prefix=f".{model_id}-", dir=target.parent)
        try:
            with os.fdopen(descriptor, "wb") as output:
                while chunk := source.read(1024 * 1024):
                    output.write(chunk)
                    digest.update(chunk)
                output.flush()
                os.fsync(output.fileno())
            os.replace(temporary_name, target)
        except Exception:
            Path(temporary_name).unlink(missing_ok=True)
            raise
        return target, digest.hexdigest()

    def create_export_staging(self, project_id: str, export_id: str) -> tuple[Path, Path]:
        root = self.ensure_project(project_id) / "exports"
        final = self._within(root / export_id)
        staging = self._within(root / f".{export_id}.staging")
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        return staging, final

    def publish_export(self, staging: Path, final: Path) -> None:
        staging = self._within(staging)
        final = self._within(final)
        if final.exists():
            shutil.rmtree(final)
        os.replace(staging, final)

    def export_file(self, project_id: str, export_id: str, filename: str) -> Path:
        path = self._within(self.project_dir(project_id) / "exports" / export_id / Path(filename).name)
        if not path.is_file():
            raise VideoResourceNotFoundError("Export file not found")
        return path

    def remove_artifacts(self, project_id: str, video_id: str, categories: tuple[str, ...]) -> None:
        project = self.ensure_project(project_id)
        for category in categories:
            directory = self._within(project / category)
            for path in directory.glob(f"{video_id}.*"):
                if path.is_file():
                    path.unlink()

    def stage_video_deletion(self, project_id: str, video_id: str) -> Path:
        """Move managed video files aside before the SQLite delete commits.

        Staging makes the cross-store workflow recoverable: the service can put
        every file back if the database transaction fails. Matching is limited
        to the generated video identifier and never follows a database path to
        an external source file.
        """

        project = self.ensure_project(project_id)
        staging = self._within(
            project / ".deleting" / f"{video_id}-{uuid4().hex}"
        )
        moved: list[tuple[Path, Path]] = []
        try:
            for category in VIDEO_SCOPED_DIRECTORIES:
                directory = self._within(project / category)
                for source in tuple(directory.iterdir()):
                    if not self._belongs_to_video(source.name, video_id):
                        continue
                    target = self._within(staging / category / source.name)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(source, target)
                    moved.append((source, target))
        except Exception:
            for source, target in reversed(moved):
                source.parent.mkdir(parents=True, exist_ok=True)
                os.replace(target, source)
            if staging.exists():
                shutil.rmtree(staging)
            raise
        return staging

    def restore_staged_video(self, project_id: str, staging: Path) -> None:
        """Restore files staged by :meth:`stage_video_deletion`."""

        project = self.ensure_project(project_id)
        staged = self._within(staging)
        if not staged.exists():
            return
        for category_dir in tuple(staged.iterdir()):
            if not category_dir.is_dir() or category_dir.name not in VIDEO_SCOPED_DIRECTORIES:
                continue
            destination = self._within(project / category_dir.name)
            destination.mkdir(parents=True, exist_ok=True)
            for source in tuple(category_dir.iterdir()):
                os.replace(source, self._within(destination / source.name))
        shutil.rmtree(staged)
        parent = staged.parent
        if parent.name == ".deleting" and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()

    def finalize_staged_video(self, staging: Path) -> None:
        """Permanently remove staged video files after the database commit."""

        staged = self._within(staging)
        if staged.exists():
            shutil.rmtree(staged)
        parent = staged.parent
        if parent.name == ".deleting" and parent.is_dir() and not any(parent.iterdir()):
            parent.rmdir()

    @staticmethod
    def _belongs_to_video(name: str, video_id: str) -> bool:
        """Match normal caches and atomic temporary files for one video ID."""

        return (
            name == video_id
            or name.startswith(f"{video_id}.")
            or name.startswith(f".{video_id}-")
            or name.startswith(f".{video_id}.")
        )

    def _within(self, path: Path) -> Path:
        resolved = path.resolve()
        try:
            resolved.relative_to(self.root)
        except ValueError as exc:
            raise VideoValidationError("Path escapes video storage root") from exc
        return resolved
