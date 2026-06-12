from pathlib import Path
import re

from backend.app.models.schemas import RenamePreviewItem
from backend.app.services import storage


NEGATIVE_PREFIX = "NEG"
UNKNOWN_PREFIX = "UNKNOWN"
MIXED_PREFIX = "MIXED"


def preview_safety_sign_renames(
    image_dir: Path,
    label_dir: Path,
    class_names: dict[int, str],
) -> list[RenamePreviewItem]:
    used_names = {path.name.lower() for path in storage.image_paths(image_dir)}
    next_numbers = _next_numbers_by_base(image_dir)
    suggestions: list[RenamePreviewItem] = []

    for image_path in storage.image_paths(image_dir):
        label_path = storage.label_path_for(label_dir, image_path.name)
        boxes = storage.read_labels(label_dir, image_path.name) if label_path.exists() else []
        class_ids = sorted({box.class_id for box in boxes if box.class_id in class_names})
        base_name, reason = _base_name_for(class_ids, class_names, label_path.exists())
        should_rename = base_name != UNKNOWN_PREFIX
        suggested_name = image_path.name
        if should_rename:
            suggested_name = _numbered_image_name(base_name, image_path.suffix.lower(), image_path.name, used_names, next_numbers)
        used_names.add(suggested_name.lower())

        suggestions.append(
            RenamePreviewItem(
                original_name=image_path.name,
                suggested_name=suggested_name,
                reason=reason,
                class_ids=class_ids,
                label_count=len(boxes),
                will_rename=should_rename and suggested_name != image_path.name,
            )
        )

    return suggestions


def apply_safety_sign_renames(
    image_dir: Path,
    label_dir: Path,
    visualization_dir: Path,
    class_names: dict[int, str],
) -> list[RenamePreviewItem]:
    suggestions = preview_safety_sign_renames(image_dir, label_dir, class_names)

    for item in suggestions:
        if not item.will_rename:
            continue

        _rename_if_exists(image_dir / item.original_name, image_dir / item.suggested_name)
        _rename_if_exists(
            storage.label_path_for(label_dir, item.original_name),
            storage.label_path_for(label_dir, item.suggested_name),
        )
        _rename_if_exists(
            storage.visualization_path_for(visualization_dir, item.original_name),
            storage.visualization_path_for(visualization_dir, item.suggested_name),
        )

    return suggestions


def _base_name_for(class_ids: list[int], class_names: dict[int, str], has_label: bool) -> tuple[str, str]:
    if not has_label:
        return NEGATIVE_PREFIX, "No label file"

    if not class_ids:
        return NEGATIVE_PREFIX, "No safety sign labels"

    if len(class_ids) == 1:
        class_id = class_ids[0]
        return _class_code(class_names[class_id]), class_names[class_id]

    return MIXED_PREFIX, "Multiple safety sign classes"


def _class_code(class_name: str) -> str:
    return class_name.split(maxsplit=1)[0]


def _numbered_image_name(
    base_name: str,
    suffix: str,
    original_name: str,
    used_names: set[str],
    next_numbers: dict[str, int],
) -> str:
    existing_match = re.fullmatch(rf"{re.escape(base_name)}_(\d+){re.escape(suffix)}", original_name, flags=re.IGNORECASE)
    if existing_match:
        return original_name

    original_lower = original_name.lower()
    index = next_numbers.get(base_name.lower(), 1)
    candidate = f"{base_name}_{index:03d}{suffix}"

    while candidate.lower() in used_names and candidate.lower() != original_lower:
        index += 1
        candidate = f"{base_name}_{index:03d}{suffix}"

    next_numbers[base_name.lower()] = index + 1

    return candidate


def _next_numbers_by_base(image_dir: Path) -> dict[str, int]:
    next_numbers: dict[str, int] = {}
    for image_path in storage.image_paths(image_dir):
        match = re.fullmatch(r"(.+?)_(\d+)", image_path.stem)
        if not match:
            continue
        base_name = match.group(1).lower()
        number = int(match.group(2))
        next_numbers[base_name] = max(next_numbers.get(base_name, 1), number + 1)
    return next_numbers


def _rename_if_exists(source: Path, destination: Path) -> None:
    if not source.exists() or source == destination:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    source.replace(destination)
