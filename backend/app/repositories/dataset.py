from pathlib import Path
from zipfile import ZipFile

from backend.app.domain.errors import (
    DatasetCollisionError,
    FilesystemOperationError,
    ImageNotFoundError,
    InvalidFilenameError,
    InvalidLabelError,
    UnsupportedImageTypeError,
)
from backend.app.domain.geometry import clamp_box
from backend.app.domain.models import BoundingBox, DatasetImage, DeleteImageResult, RenameDatasetResult


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
TEMP_RENAME_SUFFIX = ".renaming"


class DatasetRepository:
    """Filesystem persistence for images, YOLO labels, and visualizations."""

    def __init__(self, image_dir: Path, label_dir: Path, visualization_dir: Path) -> None:
        self.image_dir = image_dir
        self.label_dir = label_dir
        self.visualization_dir = visualization_dir

    def validate_image_filename(self, filename: str) -> str:
        if not filename or Path(filename).name != filename or "\\" in filename or "/" in filename:
            raise InvalidFilenameError("Invalid filename")
        if Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
            raise UnsupportedImageTypeError("Unsupported image extension")
        return filename

    def image_paths(self) -> list[Path]:
        return sorted(
            [path for path in self.image_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS],
            key=lambda path: path.name.lower(),
        )

    def image_filenames(self) -> set[str]:
        return {path.name for path in self.image_paths()}

    def ensure_unique_image_stem(self, filename: str) -> str:
        """Reject an image whose stem would share YOLO artifacts with another image."""
        safe_name = self.validate_image_filename(filename)
        matching_names = [
            path.name
            for path in self.image_paths()
            if path.stem.casefold() == Path(safe_name).stem.casefold()
        ]
        if len(matching_names) > 1:
            raise DatasetCollisionError(
                "Multiple images share the same label and visualization stem: "
                f"{', '.join(sorted(matching_names))}. Rename one image before editing dataset artifacts."
            )
        return safe_name

    def ensure_unique_image_stems(self) -> None:
        """Reject a workflow that would apply stem-based artifacts ambiguously."""
        by_stem: dict[str, list[str]] = {}
        for path in self.image_paths():
            by_stem.setdefault(path.stem.casefold(), []).append(path.name)
        duplicates = [
            names
            for names in by_stem.values()
            if len(names) > 1
        ]
        if duplicates:
            formatted = "; ".join(
                ", ".join(sorted(names))
                for names in sorted(duplicates, key=lambda names: [name.casefold() for name in names])
            )
            raise DatasetCollisionError(
                "Multiple images share label and visualization stems: "
                f"{formatted}. Rename files manually before continuing."
            )

    def image_path_for(self, filename: str) -> Path:
        return self.image_dir / self.validate_image_filename(filename)

    def label_path_for(self, filename: str) -> Path:
        self.validate_image_filename(filename)
        return self.label_dir / f"{Path(filename).stem}.txt"

    def visualization_path_for(self, filename: str) -> Path:
        self.validate_image_filename(filename)
        return self.visualization_dir / f"verified_{Path(filename).stem}.jpg"

    def visualization_file_path(self, filename: str) -> Path:
        """Return a safe requested visualization path without changing its name."""
        self.validate_image_filename(filename.removeprefix("verified_"))
        return self.visualization_dir / filename

    def list_images(self) -> list[DatasetImage]:
        return [
            DatasetImage(
                name=path.name,
                has_label=self.label_path_for(path.name).exists(),
                has_visualization=self.visualization_path_for(path.name).exists(),
            )
            for path in self.image_paths()
        ]

    def read_labels(self, filename: str) -> list[BoundingBox]:
        self.ensure_unique_image_stem(filename)
        path = self.label_path_for(filename)
        if not path.exists():
            return []

        boxes: list[BoundingBox] = []
        with path.open("r", encoding="utf-8") as label_file:
            for line_number, line in enumerate(label_file, start=1):
                parts = line.strip().split()
                if not parts:
                    continue
                if len(parts) != 5:
                    raise InvalidLabelError(f"Malformed label on line {line_number}")
                try:
                    box = BoundingBox(
                        class_id=int(parts[0]),
                        x_center=float(parts[1]),
                        y_center=float(parts[2]),
                        w=float(parts[3]),
                        h=float(parts[4]),
                    )
                except ValueError as exc:
                    raise InvalidLabelError(f"Invalid label on line {line_number}") from exc
                _validate_normalized_box(box, line_number)
                boxes.append(clamp_box(box))
        return boxes

    def save_labels(self, filename: str, boxes: list[BoundingBox]) -> None:
        self.ensure_unique_image_stem(filename)
        path = self.label_path_for(filename)
        path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            f"{box.class_id} {box.x_center:.6f} {box.y_center:.6f} {box.w:.6f} {box.h:.6f}"
            for box in (clamp_box(box) for box in boxes)
        ]
        path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")

    def ensure_label_file(self, filename: str) -> Path:
        self.ensure_unique_image_stem(filename)
        path = self.label_path_for(filename)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("", encoding="utf-8")
        return path

    def save_uploaded_image(self, filename: str, content: bytes) -> str:
        safe_name = self.validate_image_filename(Path(filename).name)
        target_path = self._unique_image_path(safe_name)
        target_path.parent.mkdir(parents=True, exist_ok=True)
        target_path.write_bytes(content)
        return target_path.name

    def delete_image_artifacts(self, filename: str) -> DeleteImageResult:
        image_path = self.image_path_for(filename)
        if not image_path.exists():
            raise ImageNotFoundError("Image not found")
        self.ensure_unique_image_stem(filename)
        try:
            for path in (
                image_path,
                self.label_path_for(filename),
                self.visualization_path_for(filename),
            ):
                if path.exists():
                    path.unlink()
        except OSError as exc:
            result = DeleteImageResult(
                filename=filename,
                filesystem_completed=False,
                reconciliation_required=True,
                warnings=("Filesystem deletion did not complete; inspect the dataset artifacts before retrying.",),
            )
            raise FilesystemOperationError("Filesystem deletion did not complete", result) from exc
        return DeleteImageResult(filename=filename, filesystem_completed=True)

    def rename_dataset_sequential(self, prefix: str = "image", start_index: int = 0) -> RenameDatasetResult:
        self._ensure_no_pending_rename_artifacts()
        self.ensure_unique_image_stems()
        images = self.image_paths()
        if not images:
            return RenameDatasetResult(filename_map={}, filesystem_completed=True)

        filename_map = {
            image_path.name: f"{prefix}_{start_index + offset:05d}{image_path.suffix.lower()}"
            for offset, image_path in enumerate(images)
        }
        self._validate_rename_plan(images, filename_map)

        try:
            pending: list[tuple[Path, Path, Path | None, Path, Path | None]] = []
            for image_path in images:
                target_image = self.image_dir / filename_map[image_path.name]
                source_label = self.label_path_for(image_path.name)
                source_visualization = self.visualization_path_for(image_path.name)
                temp_image = image_path.with_name(f"{image_path.name}{TEMP_RENAME_SUFFIX}")
                temp_label = source_label.with_name(f"{source_label.name}{TEMP_RENAME_SUFFIX}") if source_label.exists() else None
                temp_visualization = (
                    source_visualization.with_name(f"{source_visualization.name}{TEMP_RENAME_SUFFIX}")
                    if source_visualization.exists()
                    else None
                )
                pending.append((image_path, temp_image, source_label if source_label.exists() else None, target_image, source_visualization if source_visualization.exists() else None))
                image_path.rename(temp_image)
                if temp_label is not None:
                    source_label.rename(temp_label)
                if temp_visualization is not None:
                    source_visualization.rename(temp_visualization)

            for _, temp_image, source_label, target_image, source_visualization in pending:
                temp_image.rename(target_image)
                target_label = self.label_dir / f"{target_image.stem}.txt"
                if source_label is not None:
                    source_label.with_name(f"{source_label.name}{TEMP_RENAME_SUFFIX}").rename(target_label)
                else:
                    target_label.parent.mkdir(parents=True, exist_ok=True)
                    target_label.write_text("", encoding="utf-8")
                if source_visualization is not None:
                    source_visualization.with_name(f"{source_visualization.name}{TEMP_RENAME_SUFFIX}").rename(
                        self.visualization_dir / f"verified_{target_image.stem}.jpg"
                    )

            self._remove_orphan_artifacts()
        except OSError as exc:
            result = RenameDatasetResult(
                filename_map=filename_map,
                filesystem_completed=False,
                reconciliation_required=True,
                warnings=("Filesystem rename did not complete; inspect .renaming artifacts before retrying.",),
            )
            raise FilesystemOperationError("Filesystem rename did not complete", result) from exc
        return RenameDatasetResult(filename_map=filename_map, filesystem_completed=True)

    def add_image_and_label_to_zip(self, zip_file: ZipFile, filename: str) -> None:
        self.ensure_unique_image_stem(filename)
        image_path = self.image_path_for(filename)
        if not image_path.exists():
            raise ImageNotFoundError("Image not found")
        label_path = self.ensure_label_file(filename)
        zip_file.write(image_path, f"images/{image_path.name}")
        zip_file.write(label_path, f"labels/{label_path.name}")

    def _unique_image_path(self, filename: str) -> Path:
        base_path = self.image_dir / filename
        existing_stems = {path.stem.casefold() for path in self.image_paths()}
        if not base_path.exists() and base_path.stem.casefold() not in existing_stems:
            return base_path
        index = 1
        while True:
            candidate = self.image_dir / f"{base_path.stem}_{index:03d}{base_path.suffix}"
            if not candidate.exists() and candidate.stem.casefold() not in existing_stems:
                return candidate
            index += 1

    def _validate_rename_plan(self, images: list[Path], filename_map: dict[str, str]) -> None:
        target_names = set(filename_map.values())
        if len(target_names) != len(images):
            raise DatasetCollisionError("Sequential rename would create duplicate image names")

        source_images = {path.resolve() for path in images}
        source_labels = {self.label_path_for(path.name).resolve() for path in images if self.label_path_for(path.name).exists()}
        source_visualizations = {
            self.visualization_path_for(path.name).resolve()
            for path in images
            if self.visualization_path_for(path.name).exists()
        }
        for target_name in target_names:
            target_image = (self.image_dir / target_name).resolve()
            target_label = (self.label_dir / f"{Path(target_name).stem}.txt").resolve()
            target_visualization = (self.visualization_dir / f"verified_{Path(target_name).stem}.jpg").resolve()
            if target_image.exists() and target_image not in source_images:
                raise DatasetCollisionError(f"Rename target already exists: {target_image.name}")
            if target_label.exists() and target_label not in source_labels:
                raise DatasetCollisionError(f"Rename target label already exists: {target_label.name}")
            if target_visualization.exists() and target_visualization not in source_visualizations:
                raise DatasetCollisionError(f"Rename target visualization already exists: {target_visualization.name}")

    def _ensure_no_pending_rename_artifacts(self) -> None:
        pending_artifacts = [
            path
            for directory in (self.image_dir, self.label_dir, self.visualization_dir)
            for path in directory.glob(f"*{TEMP_RENAME_SUFFIX}")
            if path.is_file()
        ]
        if pending_artifacts:
            names = ", ".join(sorted(path.name for path in pending_artifacts))
            raise DatasetCollisionError(
                f"Unfinished sequential rename artifacts detected: {names}. Resolve them before retrying."
            )

    def _remove_orphan_artifacts(self) -> None:
        valid_stems = {path.stem for path in self.image_paths()}
        for label_path in self.label_dir.glob("*.txt"):
            if label_path.name != "classes.txt" and label_path.stem not in valid_stems:
                label_path.unlink(missing_ok=True)
        for visualization_path in self.visualization_dir.glob("*.jpg"):
            if visualization_path.stem.replace("verified_", "", 1) not in valid_stems:
                visualization_path.unlink(missing_ok=True)


def _validate_normalized_box(box: BoundingBox, line_number: int) -> None:
    if (
        box.class_id < 0
        or not 0 <= box.x_center <= 1
        or not 0 <= box.y_center <= 1
        or not 0 < box.w <= 1
        or not 0 < box.h <= 1
    ):
        raise InvalidLabelError(f"Invalid label on line {line_number}")
