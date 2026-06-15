import json
from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.models.schemas import BoundingBox, ImageItem


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}
TEMP_RENAME_SUFFIX = ".renaming"


def validate_image_filename(filename: str) -> str:
    if not filename or Path(filename).name != filename or "\\" in filename or "/" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    if Path(filename).suffix.lower() not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported image extension")

    return filename


def image_paths(image_dir: Path) -> list[Path]:
    return sorted(
        [path for path in image_dir.iterdir() if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS],
        key=lambda path: path.name.lower(),
    )


def label_path_for(label_dir: Path, filename: str) -> Path:
    validate_image_filename(filename)
    return label_dir / f"{Path(filename).stem}.txt"


def visualization_path_for(visualization_dir: Path, filename: str) -> Path:
    validate_image_filename(filename)
    return visualization_dir / f"verified_{Path(filename).stem}.jpg"


def _approved_file_path(label_dir: Path) -> Path:
    return label_dir / "approved.json"


def read_approvals(label_dir: Path) -> set[str]:
    path = _approved_file_path(label_dir)
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(data)
    except (json.JSONDecodeError, IOError):
        pass
    return set()


def set_approval(label_dir: Path, filename: str, is_approved: bool) -> None:
    validate_image_filename(filename)
    label_dir.mkdir(parents=True, exist_ok=True)
    approvals = read_approvals(label_dir)
    
    if is_approved:
        approvals.add(filename)
    else:
        approvals.discard(filename)
        
    path = _approved_file_path(label_dir)
    path.write_text(json.dumps(sorted(list(approvals)), indent=2), encoding="utf-8")


def list_images(image_dir: Path, label_dir: Path, visualization_dir: Path, media_prefix: str = "/media") -> list[ImageItem]:
    items: list[ImageItem] = []
    approvals = read_approvals(label_dir)
    for path in image_paths(image_dir):
        label_path = label_path_for(label_dir, path.name)
        visualization_path = visualization_path_for(visualization_dir, path.name)
        items.append(
            ImageItem(
                name=path.name,
                has_label=label_path.exists(),
                is_approved=path.name in approvals,
                image_url=f"{media_prefix}/images/{path.name}",
                visualization_url=f"{media_prefix}/visualizations/{visualization_path.name}"
                if visualization_path.exists()
                else None,
            )
        )
    return items


def read_labels(label_dir: Path, filename: str) -> list[BoundingBox]:
    path = label_path_for(label_dir, filename)
    if not path.exists():
        return []

    boxes: list[BoundingBox] = []
    with path.open("r", encoding="utf-8") as label_file:
        for line_number, line in enumerate(label_file, start=1):
            parts = line.strip().split()
            if not parts:
                continue
            if len(parts) != 5:
                raise HTTPException(status_code=422, detail=f"Malformed label on line {line_number}")
            try:
                boxes.append(
                    clamp_box(
                        BoundingBox(
                            class_id=int(parts[0]),
                            x_center=float(parts[1]),
                            y_center=float(parts[2]),
                            w=float(parts[3]),
                            h=float(parts[4]),
                        )
                    )
                )
            except (ValueError, ValidationError) as exc:
                raise HTTPException(status_code=422, detail=f"Invalid label on line {line_number}") from exc
    return boxes


def save_labels(label_dir: Path, filename: str, boxes: list[BoundingBox]) -> None:
    path = label_path_for(label_dir, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        f"{box.class_id} {box.x_center:.6f} {box.y_center:.6f} {box.w:.6f} {box.h:.6f}"
        for box in (clamp_box(box) for box in boxes)
    ]
    path.write_text(("\n".join(lines) + "\n") if lines else "", encoding="utf-8")


def ensure_label_file(label_dir: Path, filename: str) -> Path:
    path = label_path_for(label_dir, filename)
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("", encoding="utf-8")
    return path


def save_uploaded_image(image_dir: Path, filename: str, content: bytes) -> str:
    safe_name = validate_image_filename(Path(filename).name)
    target_path = unique_image_path(image_dir, safe_name)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    target_path.write_bytes(content)
    return target_path.name


def unique_image_path(image_dir: Path, filename: str) -> Path:
    base_path = image_dir / filename
    if not base_path.exists():
        return base_path

    stem = base_path.stem
    suffix = base_path.suffix
    index = 1
    while True:
        candidate = image_dir / f"{stem}_{index:03d}{suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def rename_dataset_sequential(
    image_dir: Path,
    label_dir: Path,
    visualization_dir: Path,
    prefix: str = "image",
    start_index: int = 0,
) -> int:
    images = image_paths(image_dir)
    if not images:
        return 0

    pending: list[tuple[Path, Path, Path | None, Path, Path | None, Path | None]] = []
    for offset, image_path in enumerate(images):
        target_stem = f"{prefix}_{start_index + offset:05d}"
        target_image = image_dir / f"{target_stem}{image_path.suffix.lower()}"
        source_label = label_path_for(label_dir, image_path.name)
        target_label = label_dir / f"{target_stem}.txt"
        source_visualization = visualization_path_for(visualization_dir, image_path.name)
        target_visualization = visualization_dir / f"verified_{target_stem}.jpg"

        temp_image = image_path.with_name(f"{image_path.name}{TEMP_RENAME_SUFFIX}")
        temp_label = source_label.with_name(f"{source_label.name}{TEMP_RENAME_SUFFIX}") if source_label.exists() else None
        temp_visualization = (
            source_visualization.with_name(f"{source_visualization.name}{TEMP_RENAME_SUFFIX}")
            if source_visualization.exists()
            else None
        )
        pending.append((image_path, temp_image, source_label if source_label.exists() else None, target_image, target_label, source_visualization if source_visualization.exists() else None))

        if image_path != temp_image:
            image_path.rename(temp_image)
        if source_label.exists() and temp_label is not None:
            source_label.rename(temp_label)
        if source_visualization.exists() and temp_visualization is not None:
            source_visualization.rename(temp_visualization)

    for _, temp_image, source_label, target_image, target_label, source_visualization in pending:
        if target_image.exists():
            target_image.unlink()
        temp_image.rename(target_image)

        if target_label.exists():
            target_label.unlink()
        if source_label is not None:
            temp_label = source_label.with_name(f"{source_label.name}{TEMP_RENAME_SUFFIX}")
            temp_label.rename(target_label)
        else:
            target_label.parent.mkdir(parents=True, exist_ok=True)
            target_label.write_text("", encoding="utf-8")

        if source_visualization is not None:
            temp_visualization = source_visualization.with_name(f"{source_visualization.name}{TEMP_RENAME_SUFFIX}")
            target_visualization = visualization_dir / f"verified_{target_image.stem}.jpg"
            target_visualization.parent.mkdir(parents=True, exist_ok=True)
            if target_visualization.exists():
                target_visualization.unlink()
            temp_visualization.rename(target_visualization)

    # Clean up orphan labels and visualizations
    valid_stems = {img.stem for img in image_paths(image_dir)}
    for label_path in label_dir.glob("*.txt"):
        if label_path.name not in ["classes.txt"] and label_path.stem not in valid_stems:
            try:
                label_path.unlink()
            except OSError:
                pass

    for vis_path in visualization_dir.glob("*.jpg"):
        if vis_path.stem.replace("verified_", "", 1) not in valid_stems:
            try:
                vis_path.unlink()
            except OSError:
                pass

    return len(images)


def copy_image_and_label_to_zip(zip_file, image_dir: Path, label_dir: Path, filename: str) -> None:
    validate_image_filename(filename)
    image_path = image_dir / filename
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Image not found")

    label_path = ensure_label_file(label_dir, filename)
    zip_file.write(image_path, f"images/{image_path.name}")
    zip_file.write(label_path, f"labels/{label_path.name}")


def validate_label_classes(boxes: list[BoundingBox], allowed_class_ids: set[int]) -> None:
    invalid_class_ids = sorted({box.class_id for box in boxes if box.class_id not in allowed_class_ids})
    if invalid_class_ids:
        allowed = ", ".join(str(class_id) for class_id in sorted(allowed_class_ids))
        invalid = ", ".join(str(class_id) for class_id in invalid_class_ids)
        raise HTTPException(status_code=422, detail=f"Invalid class ID(s): {invalid}. Allowed class IDs: {allowed}")


def delete_image_artifacts(image_dir: Path, label_dir: Path, visualization_dir: Path, filename: str) -> None:
    validate_image_filename(filename)
    for path in (
        image_dir / filename,
        label_path_for(label_dir, filename),
        visualization_path_for(visualization_dir, filename),
    ):
        if path.exists():
            path.unlink()
            
    # Also remove from approvals
    approvals = read_approvals(label_dir)
    if filename in approvals:
        approvals.remove(filename)
        path = _approved_file_path(label_dir)
        path.write_text(json.dumps(sorted(list(approvals)), indent=2), encoding="utf-8")


def clamp_box(box: BoundingBox) -> BoundingBox:
    x1 = max(0.0, box.x_center - box.w / 2)
    y1 = max(0.0, box.y_center - box.h / 2)
    x2 = min(1.0, box.x_center + box.w / 2)
    y2 = min(1.0, box.y_center + box.h / 2)

    width = max(0.000001, x2 - x1)
    height = max(0.000001, y2 - y1)
    return BoundingBox(
        class_id=box.class_id,
        x_center=round(x1 + width / 2, 6),
        y_center=round(y1 + height / 2, 6),
        w=round(width, 6),
        h=round(height, 6),
    )
