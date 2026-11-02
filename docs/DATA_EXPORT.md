# Data export contract

Exports transfer labeled samples to a separate training workflow. They do not
replace a full workspace backup and do not create train/validation/test splits.
Keep source grouping information so the training team can avoid leakage between
related images, clips or overlapping windows.

## PPE and Sign images

The UI's `Export Dataset` action and the single/all-image API exports produce ZIP contents:

```text
images/<filename>
labels/<matching-stem>.txt
```

YOLO text rows are `class_id x_center y_center width height`, with coordinates
normalized to image dimensions. Files with no saved labels export as empty text
files. Approval is not an export filter and is not included as a review report.

Default PPE IDs: `0=Person`, `1=Helmet`, `2=Vest`, `3=Cleaning Coverall`.
Default Sign IDs: `0=M014 Wear head protection`, `1=M015 Wear high-visibility
clothing`, `2=P004 No thoroughfare`, `3=W011 Slippery surface`.
Configured maps override those defaults; deliver the actual map with the ZIP.

## Behavior video samples

In a labeling project, validate and create an export. A worker builds it in a
staging directory and publishes only after completion. Download the completed
ZIP; a queued/running export is not a completed deliverable.

Only videos marked both included and approved contribute. Validation requires
at least one such video, ready features and generated windows. Unapproved videos
are excluded with warnings. Read all unresolved/quality warnings before export.
Annotation rows require segment inclusion; window samples require inclusion and
a resolved label. Do not assume every detected frame becomes a training sample.
Default mixed-window label rules evaluate falling before running, then others;
the project configuration supplies the overlap thresholds.

| File | Contents |
|---|---|
| `annotations.jsonl` | Included segments: video ID, track ID, inclusive start/end frame, label and annotation version |
| `keypoint_windows.npz` | Arrays: `keypoints` (N,60,17,2), `keypoint_scores` (N,60,17), `bboxes` (N,60,4), integer `labels`, and `video_ids` |
| `manifest.json` | Class map, source-video hashes, pose/tracking/window settings, schema/application versions, timestamp and payload hashes/sizes |

The canonical timeline is 24 FPS, with 60-frame windows and stride 12. Class IDs
are `0=others`, `1=running`, `2=falling`. Missing pose frames are zero-filled in
the NPZ. The export does not embed raw videos, a complete project DB, model
weights, or the entire feature cache. See the manifest for reproducibility
settings and [DATABASE](DATABASE.md) for storage boundaries.

## Delivery to the training team

Provide the export, its hash, generating commit, class mapping, source grouping,
review status, known quality issues and authorized data-use context. The training
owner supplies split policy, training code/environment, preprocessing and
evaluation evidence. Do not equate application acceptance with model evaluation.
