"""Standalone script to extract the 141 pre-engineered posture and locomotion features
(excluding track_gap_count and valid_frame_ratio) from raw exported keypoint windows
across multiple sub-datasets, merge them, split them using a database-independent
overlap track clustering method, and save them into 3 distinct split .npz files.

Usage:
    python extract_engineered_features.py
"""

from __future__ import annotations

import sys
from pathlib import Path
import numpy as np

# Ensure main repository root is in python path
behaviors_datasets_dir = Path(__file__).resolve().parent
project_root = behaviors_datasets_dir.parent
sys.path.append(str(project_root))

from backend.app.services.video_features import extract_window_features, feature_columns


def main():
    export_dir = behaviors_datasets_dir / "raw_data"
    
    # 3 distinct output files saved to features_extracted_data directory
    train_file = behaviors_datasets_dir / "features_extracted_data" / "train_split.npz"
    val_file = behaviors_datasets_dir / "features_extracted_data" / "val_split.npz"
    test_file = behaviors_datasets_dir / "features_extracted_data" / "test_split.npz"

    subdirs = ["fall", "no-fall", "run"]
    
    keypoints_list = []
    bboxes_list = []
    scores_list = []
    labels_list = []
    
    groups = []
    global_window_offset = 0
    
    # Store video IDs mapping for each window
    window_video_ids = []

    print("=" * 60)
    print(" LOADING AND MERGING DATASETS")
    print("=" * 60)

    for folder_name in subdirs:
        folder_path = export_dir / folder_name
        npz_path = folder_path / "keypoint_windows.npz"
        if not npz_path.exists():
            print(f"Warning: Subdirectory export not found at {npz_path}. Skipping.")
            continue
            
        print(f"Loading sub-dataset: {folder_name}...")
        npz_data = dict(np.load(npz_path, allow_pickle=True))
        
        kps = npz_data["keypoints"]  # (N, 60, 17, 2)
        bbs = npz_data["bboxes"]     # (N, 60, 4)
        scs = npz_data["keypoint_scores"] # (N, 60, 17)
        lbls = npz_data["labels"]    # (N,)
        
        n_win = len(lbls)
        print(f"  - Loaded {n_win} windows.")
        
        keypoints_list.append(kps)
        bboxes_list.append(bbs)
        scores_list.append(scs)
        labels_list.append(lbls)
        
        # 3. Track Clustering & Video ID Extraction (Per Sub-dataset)
        # Group windows into contiguous tracks strictly within this sub-dataset boundary
        local_groups = []
        current_group = [global_window_offset]
        for i in range(n_win - 1):
            w_curr = kps[i, 12:60]
            w_next = kps[i+1, 0:48]
            
            # Map index to the final merged array
            curr_idx = global_window_offset + i
            next_idx = global_window_offset + i + 1
            
            if np.allclose(w_curr, w_next, atol=1e-4):
                current_group.append(next_idx)
            else:
                local_groups.append(current_group)
                current_group = [next_idx]
        local_groups.append(current_group)
        
        print(f"  - Segmented sub-dataset into {len(local_groups)} trajectories.")
        
        # Assign synthetic video IDs to windows based on their trajectory groups
        local_video_ids = [None] * n_win
        for local_group_idx, g_indices in enumerate(local_groups):
            # Each trajectory group represents a unique track (person) from a unique video segment
            video_name = f"{folder_name}_video_{local_group_idx}"
            for idx in g_indices:
                local_idx = idx - global_window_offset
                local_video_ids[local_idx] = video_name
                
        # If the NPZ file contains real video IDs, override synthetic IDs (except for unknowns)
        if "video_ids" in npz_data:
            real_vids = npz_data["video_ids"]
            for i in range(n_win):
                vid = str(real_vids[i])
                if vid and vid != "unknown_video" and vid != "None":
                    local_video_ids[i] = vid
                    
        window_video_ids.extend(local_video_ids)
        global_window_offset += n_win

    if not labels_list:
        print("Error: No keypoint_windows.npz files loaded. Cannot proceed.")
        return

    # Concatenate all datasets
    raw_keypoints = np.concatenate(keypoints_list, axis=0)
    bboxes = np.concatenate(bboxes_list, axis=0)
    keypoint_scores = np.concatenate(scores_list, axis=0)
    labels = np.concatenate(labels_list, axis=0)
    video_ids_array = np.array(window_video_ids, dtype=object)

    num_windows = len(labels)
    
    # Group window indices by resolved video ID to ensure leakage-free video-level splitting
    video_to_indices = {}
    for idx, vid in enumerate(window_video_ids):
        video_to_indices.setdefault(vid, []).append(idx)
    groups = list(video_to_indices.values())
    
    # Exclude 'track_gap_count' and 'valid_frame_ratio' from features list
    exclude_features = {"track_gap_count", "valid_frame_ratio"}
    columns = [col for col in feature_columns() if col not in exclude_features]
    
    print("\n" + "=" * 60)
    print(" COMBINED DATASET STATISTICS")
    print("=" * 60)
    print(f"Total merged windows        : {num_windows}")
    print(f"Total merged trajectories   : {len(groups)}")
    print(f"Target feature vector size  : {len(columns)} columns (track_gap_count & valid_frame_ratio excluded)")
    print("-" * 60)
    unique_classes, counts = np.unique(labels, return_counts=True)
    class_dist_str = ", ".join(f"Class {c}: {cnt}" for c, cnt in zip(unique_classes, counts))
    print(f"Combined class distribution : {class_dist_str}")
    print("=" * 60)

    # 2. Extract features using video_features.py
    print("\nExtracting Group A-E features for all windows...")
    X_engineered = np.zeros((num_windows, len(columns)), dtype=np.float32)
    
    null_or_gap_samples = []

    for i in range(num_windows):
        frames = []
        for f in range(60):
            frames.append({
                "bbox": bboxes[i, f].tolist(),
                "keypoints": raw_keypoints[i, f].tolist(),
                "keypoint_scores": keypoint_scores[i, f].tolist()
            })
        
        # Calculate raw window features
        features_dict = extract_window_features(frames)
        raw_features = features_dict["raw"]

        null_cols = []
        # Store in matrix in matching index order (excluding track_gap_count and valid_frame_ratio)
        for col_idx, col_name in enumerate(columns):
            val = raw_features.get(col_name)
            if val is None:
                null_cols.append(col_name)
                X_engineered[i, col_idx] = 0.0
            else:
                X_engineered[i, col_idx] = float(val)

        # Check for NULLs or other gap indicators if they ever arise
        gap_count = raw_features.get("track_gap_count", 0.0)
        if len(null_cols) > 0 or (gap_count is not None and gap_count > 0):
            null_or_gap_samples.append({
                "window_index": i,
                "null_columns": null_cols,
                "track_gap_count": gap_count if gap_count is not None else 0.0,
                "label": int(labels[i])
            })

        if (i + 1) % 400 == 0 or (i + 1) == num_windows:
            print(f"  - Extracted features for {i + 1}/{num_windows} windows...")

    # Post-process: Normalize/clamp hip_ankle vertical ratios to [0.0, 1.0] if they exceed 1.0
    print("\nNormalizing hip_ankle vertical ratios (capping values > 1.0 to 1.0)...")
    clamped_cols = 0
    for col_idx, col_name in enumerate(columns):
        if col_name == "hip_ankle_vertical_diff_mean" or col_name.startswith("step_hip_ankle_"):
            X_engineered[:, col_idx] = np.clip(X_engineered[:, col_idx], 0.0, 1.0)
            clamped_cols += 1
    print(f"  - Clamped values in {clamped_cols} hip_ankle columns to a maximum of 1.0.")

    # Print samples containing NULL values or track_gap_count > 0
    print("\n" + "=" * 60)
    print(" SAMPLES WITH NULL VALUES OR TRACK GAP COUNT > 0")
    print("=" * 60)
    print(f"Total such samples found: {len(null_or_gap_samples)} out of {num_windows} windows.")
    
    if len(null_or_gap_samples) > 0:
        print(f"\nListing first 15 samples:")
        print(f"{'Index':<8} | {'Label':<5} | {'Gap Count':<9} | {'NULL Cols count':<15} | {'NULL Columns'}")
        print("-" * 80)
        for s in null_or_gap_samples[:15]:
            null_cols_str = ", ".join(s["null_columns"]) if s["null_columns"] else "None"
            if len(null_cols_str) > 40:
                null_cols_str = null_cols_str[:37] + "..."
            print(f"{s['window_index']:<8} | {s['label']:<5} | {s['track_gap_count']:<9.1f} | {len(s['null_columns']):<15} | {null_cols_str}")
    print("=" * 60)

    # 4. Stratified Leakage-Free Splitting
    # For the dataset splitting process, the outputs (train, val, test) should have 
    # the same distribution of class samples as the overall dataset (approx 70/15/15 split).
    # We do a greedy stratified group assignment based on relative deficit normalization.
    
    # Calculate the class distribution of each trajectory group
    group_class_counts = []
    for g in groups:
        counts_dict = {0: 0, 1: 0, 2: 0}
        for idx in g:
            lbl = int(labels[idx])
            counts_dict[lbl] = counts_dict.get(lbl, 0) + 1
        group_class_counts.append(counts_dict)
        
    # Get total count per class
    unique_classes, total_counts = np.unique(labels, return_counts=True)
    class_totals = {int(c): int(count) for c, count in zip(unique_classes, total_counts)}
    
    # Target ratios and counts per split per class
    ratios = {"train": 0.70, "val": 0.15, "test": 0.15}
    targets = {
        split: {c: ratios[split] * class_totals.get(c, 0) for c in class_totals}
        for split in ratios
    }
    
    # Current accumulated counts per split per class
    current_counts = {
        split: {c: 0 for c in class_totals}
        for split in ratios
    }
    
    # Shuffle the group order with a fixed seed for reproducibility
    np.random.seed(42)
    group_indices = np.arange(len(groups))
    np.random.shuffle(group_indices)
    
    train_idx = []
    val_idx = []
    test_idx = []
    split_indices = {"train": train_idx, "val": val_idx, "test": test_idx}
    
    for g_idx in group_indices:
        g = groups[g_idx]
        counts = group_class_counts[g_idx]
        
        best_split = None
        best_score = -float("inf")
        
        # Decide split assignment by maximizing relative deficit dot product
        for split in ["train", "val", "test"]:
            score = 0.0
            for c in class_totals:
                count_in_group = counts.get(c, 0)
                if count_in_group > 0:
                    deficit = targets[split][c] - current_counts[split][c]
                    # Normalize deficit by global class totals to keep classes of different scales balanced
                    normalized_deficit = deficit / class_totals[c]
                    score += count_in_group * normalized_deficit
            
            if score > best_score:
                best_score = score
                best_split = split
                
        if best_split is None:
            best_split = "train"
            
        # Assign group to the chosen split
        split_indices[best_split].extend(g)
        for c in class_totals:
            current_counts[best_split][c] += counts.get(c, 0)

    # 5. Print Validation Samples
    print("\n" + "=" * 60)
    print(" SAMPLE FEATURE VALIDATION (First Window in Train split)")
    print("=" * 60)
    print(f"Train Label   : {labels[train_idx[0]]}")
    print(f"Train Video ID: {video_ids_array[train_idx[0]]}")
    print("First 10 pre-engineered feature values:")
    for col_idx in range(10):
        name = columns[col_idx]
        val = X_engineered[train_idx[0], col_idx]
        print(f"  - {name:<30} : {val:.6f}")
    print("=" * 60)

    # 6. Save splits into 3 distinct files
    np.savez_compressed(train_file, X=X_engineered[train_idx], y=labels[train_idx], video_ids=video_ids_array[train_idx])
    np.savez_compressed(val_file, X=X_engineered[val_idx], y=labels[val_idx], video_ids=video_ids_array[val_idx])
    np.savez_compressed(test_file, X=X_engineered[test_idx], y=labels[test_idx], video_ids=video_ids_array[test_idx])
    
    print("\nSuccessfully saved splits to:")
    print(f"  - Train: {train_file.absolute()}")
    print(f"  - Val  : {val_file.absolute()}")
    print(f"  - Test : {test_file.absolute()}")


if __name__ == "__main__":
    main()
