from pathlib import Path

from backend.app.services import renaming


CLASS_NAMES = {
    0: "M014 Wear head protection",
    1: "M015 Wear high-visibility clothing",
    2: "P004 No thoroughfare",
    3: "W011 Slippery surface",
}


def test_preview_safety_sign_renames_uses_single_class_label(tmp_path: Path) -> None:
    image_dir = tmp_path / "images"
    label_dir = tmp_path / "labels"
    image_dir.mkdir()
    label_dir.mkdir()
    (image_dir / "camera-shot.jpg").write_bytes(b"image")
    (label_dir / "camera-shot.txt").write_text("1 0.5 0.5 0.2 0.2\n", encoding="utf-8")

    items = renaming.preview_safety_sign_renames(image_dir, label_dir, CLASS_NAMES)

    assert len(items) == 1
    assert items[0].suggested_name == "M015_001.jpg"
    assert items[0].reason == "M015 Wear high-visibility clothing"
    assert items[0].class_ids == [1]
    assert items[0].will_rename is True


def test_preview_safety_sign_renames_handles_mixed_and_unknown_labels(tmp_path: Path) -> None:
    image_dir = tmp_path / "images"
    label_dir = tmp_path / "labels"
    image_dir.mkdir()
    label_dir.mkdir()
    (image_dir / "empty.png").write_bytes(b"image")
    (image_dir / "mixed.png").write_bytes(b"image")
    (label_dir / "empty.txt").write_text("", encoding="utf-8")
    (label_dir / "mixed.txt").write_text(
        "0 0.2 0.2 0.1 0.1\n3 0.7 0.7 0.1 0.1\n",
        encoding="utf-8",
    )

    items = renaming.preview_safety_sign_renames(image_dir, label_dir, CLASS_NAMES)

    assert [item.suggested_name for item in items] == ["NEG_001.png", "MIXED_001.png"]
    assert [item.will_rename for item in items] == [True, True]


def test_apply_safety_sign_renames_moves_image_label_and_visualization(tmp_path: Path) -> None:
    image_dir = tmp_path / "images"
    label_dir = tmp_path / "labels"
    visualization_dir = tmp_path / "visualizations"
    image_dir.mkdir()
    label_dir.mkdir()
    visualization_dir.mkdir()
    (image_dir / "manual.jpg").write_bytes(b"image")
    (label_dir / "manual.txt").write_text("2 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (visualization_dir / "verified_manual.jpg").write_bytes(b"visual")

    renaming.apply_safety_sign_renames(image_dir, label_dir, visualization_dir, CLASS_NAMES)

    assert (image_dir / "P004_001.jpg").exists()
    assert (label_dir / "P004_001.txt").exists()
    assert (visualization_dir / "verified_P004_001.jpg").exists()
    assert not (image_dir / "manual.jpg").exists()


def test_apply_safety_sign_renames_creates_empty_negative_label(tmp_path: Path) -> None:
    image_dir = tmp_path / "images"
    label_dir = tmp_path / "labels"
    visualization_dir = tmp_path / "visualizations"
    image_dir.mkdir()
    label_dir.mkdir()
    visualization_dir.mkdir()
    (image_dir / "no-sign.jpg").write_bytes(b"image")

    renaming.apply_safety_sign_renames(image_dir, label_dir, visualization_dir, CLASS_NAMES)

    assert (image_dir / "NEG_001.jpg").exists()
    assert (label_dir / "NEG_001.txt").exists()
    assert (label_dir / "NEG_001.txt").read_text(encoding="utf-8") == ""


def test_preview_safety_sign_renames_avoids_existing_name_collisions(tmp_path: Path) -> None:
    image_dir = tmp_path / "images"
    label_dir = tmp_path / "labels"
    image_dir.mkdir()
    label_dir.mkdir()
    (image_dir / "M014_001.jpg").write_bytes(b"image")
    (image_dir / "camera.jpg").write_bytes(b"image")
    (label_dir / "M014_001.txt").write_text("0 0.5 0.5 0.2 0.2\n", encoding="utf-8")
    (label_dir / "camera.txt").write_text("0 0.4 0.4 0.2 0.2\n", encoding="utf-8")

    items = renaming.preview_safety_sign_renames(image_dir, label_dir, CLASS_NAMES)

    by_original = {item.original_name: item for item in items}
    assert by_original["M014_001.jpg"].will_rename is False
    assert by_original["camera.jpg"].suggested_name == "M014_002.jpg"
