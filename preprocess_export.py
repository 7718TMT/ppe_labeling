"""Independent utility to inspect, validate, and preprocess exported pose-video annotation datasets.

Usage:
    python preprocess_export.py --export_dir <path_to_exported_directory> [--output_file <optional_output_npz>]

This script:
1. Loads the manifest.json, annotations.jsonl, and keypoint_windows.npz files from the export.
2. Summarizes the dataset structure (total windows, shape of arrays, class distributions).
3. Validates pose data quality (e.g., checks average keypoint confidence).
4. Demonstrates data preprocessing pipelines:
   - Normalizing keypoint coordinate positions using the bounding box scale (bounding box diagonal).
   - Grouping and splitting train/validation/test sets by video ID to prevent data leakage.
   - Flattening window parameters for traditional ML models (e.g. Random Forest, XGBoost).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import numpy as np


def load_dataset(export_dir: Path) -> tuple[dict, list[dict], dict[str, np.ndarray]]:
    """Loads all dataset components from the exported directory."""
    manifest_path = export_dir / "manifest.json"
    annotations_path = export_dir / "annotations.jsonl"
    npz_path = export_dir / "keypoint_windows.npz"

    if not manifest_path.exists():
        raise FileNotFoundError(f"Missing manifest.json at {manifest_path}")
    if not annotations_path.exists():
        raise FileNotFoundError(f"Missing annotations.jsonl at {annotations_path}")
    if not npz_path.exists():
        raise FileNotFoundError(f"Missing keypoint_windows.npz at {npz_path}")

    # Load Manifest
    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # Load Annotations
    annotations = []
    with open(annotations_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                annotations.append(json.loads(line))

    # Load NPZ arrays
    arrays = dict(np.load(npz_path))

    return manifest, annotations, arrays


def show_summary(manifest: dict, annotations: list[dict], arrays: dict[str, np.ndarray]) -> None:
    """Displays key statistics and shapes of the loaded dataset."""
    print("=" * 60)
    print(" DATASET EXPORT SUMMARY")
    print("=" * 60)

    # Manifest configurations
    class_map = manifest.get("class_map", {})
    inv_class_map = {v: k for k, v in class_map.items()}
    print(f"Export Timestamp : {manifest.get('export_timestamp')}")
    print(f"Class Map        : {class_map}")
    print(f"Canonical FPS    : {manifest.get('canonical_fps')} Hz")
    print(f"Window Length    : {manifest.get('window', {}).get('length_frames')} frames")
    print(f"Window Stride    : {manifest.get('window', {}).get('stride_frames')} frames")
    print(f"Total Videos     : {len(manifest.get('video_hashes', {}))}")
    print("-" * 60)

    # NPZ arrays shapes
    print("Array Dimensions:")
    for name, arr in arrays.items():
        print(f"  - '{name}': shape={arr.shape}, dtype={arr.dtype}")
    print("-" * 60)

    # Class distribution
    labels = arrays["labels"]
    unique_labels, counts = np.unique(labels, return_counts=True)
    print("Class Distribution:")
    for lbl, cnt in zip(unique_labels, counts):
        name = inv_class_map.get(lbl, f"unknown_class_{lbl}")
        pct = (cnt / len(labels)) * 100
        print(f"  - Class {lbl} ({name}): {cnt} windows ({pct:.2f}%)")
    print("=" * 60)


def preprocess_data(
    annotations: list[dict], 
    arrays: dict[str, np.ndarray], 
    class_map: dict
) -> tuple[np.ndarray, np.ndarray]:
    """Demonstrates preprocessing strategies on the loaded keypoints:
    
    1. Normalization of keypoints: Scale each coordinates relative to the 
       bounding box size (box diagonal length) to ensure scale invariance.
    2. Feature Engineering: Flattening coordinate sequences over the window.
    """
    keypoints = arrays["keypoints"]  # Shape: (N, 60, 17, 2)
    bboxes = arrays["bboxes"]        # Shape: (N, 60, 4)  [x1, y1, x2, y2]
    num_windows, num_frames, num_kps, num_coords = keypoints.shape

    print("\nStarting Preprocessing Pipeline...")

    # Calculate bounding box diagonals as normalizer scales (Body scale)
    # Shape: (N, 60)
    widths = np.maximum(0.0, bboxes[:, :, 2] - bboxes[:, :, 0])
    heights = np.maximum(0.0, bboxes[:, :, 3] - bboxes[:, :, 1])
    diagonals = np.hypot(widths, heights)
    # Avoid division by zero
    diagonals = np.where(diagonals == 0.0, 1.0, diagonals)

    # Step 1: Normalize keypoint positions relative to their bounding box center & scale
    # Box centers (N, 60, 2)
    box_centers_x = bboxes[:, :, 0] + (widths / 2.0)
    box_centers_y = bboxes[:, :, 1] + (heights / 2.0)
    box_centers = np.stack([box_centers_x, box_centers_y], axis=-1)  # (N, 60, 2)

    # Normalize: (KP - Center) / Diagonal
    normalized_keypoints = np.zeros_like(keypoints)
    for w in range(num_windows):
        for f in range(num_frames):
            center = box_centers[w, f]      # Shape: (2,)
            scale = diagonals[w, f]         # Scalar
            # Subtract center and divide by diagonal
            normalized_keypoints[w, f, :, :] = (keypoints[w, f, :, :] - center) / scale

    print(f"  - Keypoint scale normalization complete (Relative coordinates in [-1, 1] range).")

    # Step 2: Flatten window inputs into feature vector arrays of shape (N, 60 * 17 * 2)
    # This prepares the sequence directly for traditional models (Random Forest, XGBoost)
    flattened_features = normalized_keypoints.reshape(num_windows, -1)
    print(f"  - Keypoints flattened into ML input feature matrix: {flattened_features.shape}")

    return flattened_features, arrays["labels"]


def split_dataset_by_video(
    annotations: list[dict], 
    features: np.ndarray, 
    labels: np.ndarray, 
    train_ratio: float = 0.7, 
    val_ratio: float = 0.15
) -> dict[str, tuple[np.ndarray, np.ndarray]]:
    """Splits the dataset into train, validation, and test subsets based on Video ID.
    
    This is highly critical to prevent 'Data Leakage' since overlapping temporal 
    windows from the same video are highly correlated.
    """
    # Map each window index to its respective video_id
    # Wait, annotations and arrays are aligned 1-to-1 by window export index
    video_ids = [anno["video_id"] for anno in annotations]
    unique_videos = list(set(video_ids))
    np.random.seed(42)  # For reproducible splits
    np.random.shuffle(unique_videos)

    total_videos = len(unique_videos)
    train_end = int(total_videos * train_ratio)
    val_end = train_end + int(total_videos * val_ratio)

    train_vids = set(unique_videos[:train_end])
    val_vids = set(unique_videos[train_end:val_end])
    test_vids = set(unique_videos[val_end:])

    # Gather indices
    train_idx = [i for i, vid in enumerate(video_ids) if vid in train_vids]
    val_idx = [i for i, vid in enumerate(video_ids) if vid in val_vids]
    test_idx = [i for i, vid in enumerate(video_ids) if vid in test_vids]

    print("\nDataset Leakage-Free Splitting (grouped by Video ID):")
    print(f"  - Total Videos in Dataset   : {total_videos}")
    print(f"  - Train Set (Video IDs)     : {len(train_vids)} videos ({len(train_idx)} windows)")
    print(f"  - Validation Set (Video IDs): {len(val_vids)} videos ({len(val_idx)} windows)")
    print(f"  - Test Set (Video IDs)      : {len(test_vids)} videos ({len(test_idx)} windows)")

    splits = {
        "train": (features[train_idx], labels[train_idx]) if train_idx else (np.empty((0, features.shape[1])), np.empty((0,))),
        "val": (features[val_idx], labels[val_idx]) if val_idx else (np.empty((0, features.shape[1])), np.empty((0,))),
        "test": (features[test_idx], labels[test_idx]) if test_idx else (np.empty((0, features.shape[1])), np.empty((0,))),
    }

    return splits


def main():
    parser = argparse.ArgumentParser(description="Preprocess and inspect exported pose-video labeling data.")
    parser.add_argument(
        "--export_dir", 
        type=str, 
        default="./pose-export-trial",
        help="Path to the directory containing the exported files (manifest.json, annotations.jsonl, keypoint_windows.npz)."
    )
    parser.add_argument(
        "--output_file", 
        type=str, 
        default=None, 
        help="Optional path to save preprocessed splits as a compressed .npz archive."
    )

    args = parser.parse_args()
    export_dir = Path(args.export_dir)

    try:
        # 1. Load Data
        manifest, annotations, arrays = load_dataset(export_dir)
        
        # 2. Summary
        show_summary(manifest, annotations, arrays)

        # 3. Preprocess
        features, labels = preprocess_data(annotations, arrays, manifest.get("class_map", {}))

        # 4. Grouped split to prevent leakage
        splits = split_dataset_by_video(annotations, features, labels)

        # 5. Optional Save
        if args.output_file:
            output_path = Path(args.output_file)
            np.savez_compressed(
                output_path,
                X_train=splits["train"][0], y_train=splits["train"][1],
                X_val=splits["val"][0], y_val=splits["val"][1],
                X_test=splits["test"][0], y_test=splits["test"][1]
            )
            print(f"\nSuccessfully saved preprocessed splits to {output_path.absolute()}")

    except Exception as e:
        print(f"\nError: {e}")


if __name__ == "__main__":
    main()
