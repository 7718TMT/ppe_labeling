from pathlib import Path

from fastapi import HTTPException
from pydantic import ValidationError

from backend.app.models.schemas import BoundingBox, ImageItem


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png"}


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


def list_images(image_dir: Path, label_dir: Path, visualization_dir: Path) -> list[ImageItem]:
    items: list[ImageItem] = []
    for path in image_paths(image_dir):
        label_path = label_path_for(label_dir, path.name)
        visualization_path = visualization_path_for(visualization_dir, path.name)
        items.append(
            ImageItem(
                name=path.name,
                has_label=label_path.exists(),
                image_url=f"/media/images/{path.name}",
                visualization_url=f"/media/visualizations/{visualization_path.name}"
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


def delete_image_artifacts(image_dir: Path, label_dir: Path, visualization_dir: Path, filename: str) -> None:
    validate_image_filename(filename)
    for path in (
        image_dir / filename,
        label_path_for(label_dir, filename),
        visualization_path_for(visualization_dir, filename),
    ):
        if path.exists():
            path.unlink()


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
