# Configuration reference

<!-- BEGIN GENERATED NOTICE -->
> **Generated file — do not edit by hand.**
> Produced by `backend/scripts/generate_docs.py` from `backend/app/core/config.py`, `.env.example`.
> Regenerate after changing those sources; edit the generator scripts, not this file.
> Run `uv run python -m backend.scripts.generate_docs`.
>
> Generated 2026-10-30 at commit `4d2ea6fc58f9`.
> Commit identifies the checkout; output may include uncommitted source changes.
<!-- END GENERATED NOTICE -->

Run commands from the repository root. Relative paths resolve against that working
directory. Copy `.env.example` to `.env` for local operation; this generator never
reads `.env` or environment overrides. Defaults below come from `Settings`.

Class maps use `ID=Name` separated by `|`. Model outputs must use the same IDs.
Device, tracker, confidence and image-size changes can affect quality; benchmark
before changing them. See [operations](OPERATIONS.md) for execution and storage.

Regenerate with `uv run python -m backend.scripts.generate_docs`.

<!-- BEGIN GENERATED -->
| Variable | Type | Code default | .env.example |
|---|---|---|---|
| `CORS_ORIGINS` | string | "http://localhost:5173" | http://localhost:5173 |
| `INFERENCE_DEVICE` | string | "auto" | auto |
| `DATABASE_PATH` | string | "data/labeling_db.sqlite3" | data/labeling_db.sqlite3 |
| `VIDEO_STORAGE_ROOT` | string | "data/video_labeling" | data/video_labeling |
| `POSE_MODEL_PATH` | string | "weights/pose.pt" | weights/pose.pt |
| `BEHAVIOR_MODEL_PATH` | string | "weights/behavior.joblib" | weights/behavior.joblib |
| `BEHAVIOR_MODEL_MANIFEST_PATH` | string / null | null | weights/behavior.manifest.json (commented example) |
| `VIDEO_WORKER_CONCURRENCY` | integer | 1 | 1 |
| `IMAGE_INFERENCE_STORAGE_ROOT` | string | "data/image_inference" | data/image_inference |
| `PPE_MODEL_PATH` | string | "weights/ppe.pt" | weights/ppe.pt |
| `PPE_IMAGE_DIR` | string | "data/ppe/images" | data/ppe/images |
| `PPE_LABEL_DIR` | string | "data/ppe/labels" | data/ppe/labels |
| `PPE_VISUALIZATION_DIR` | string | "data/ppe/labeled_images" | data/ppe/labeled_images |
| `PPE_YOLO_IMG_SIZE` | integer | 640 | 640 |
| `PPE_YOLO_CONF` | number | 0.25 | 0.25 |
| `PPE_YOLO_IOU` | number | 0.7 | 0.7 |
| `PPE_CLASS_NAMES` | string | "0=Person&#124;1=Helmet&#124;2=Vest&#124;3=Cleaning Coverall" | 0=Person&#124;1=Helmet&#124;2=Vest&#124;3=Cleaning Coverall |
| `PPE_USE_COLOR_VEST_FALLBACK` | boolean | false | false |
| `SAFETY_SIGN_MODEL_PATH` | string | "weights/sign.pt" | weights/sign.pt |
| `SAFETY_SIGN_IMAGE_DIR` | string | "data/safety_signs/images" | data/safety_signs/images |
| `SAFETY_SIGN_LABEL_DIR` | string | "data/safety_signs/labels" | data/safety_signs/labels |
| `SAFETY_SIGN_VISUALIZATION_DIR` | string | "data/safety_signs/labeled_images" | data/safety_signs/labeled_images |
| `SAFETY_SIGN_CONF` | number | 0.15 | 0.15 |
| `SAFETY_SIGN_IMG_SIZE` | integer | 640 | 640 |
| `SAFETY_SIGN_IOU` | number | 0.7 | 0.7 |
| `SAFETY_SIGN_CLASS_NAMES` | string | "0=M014 Wear head protection&#124;1=M015 Wear high-visibility clothing&#124;2=P004 No thoroughfare&#124;3=W011 Slippery surface" | 0=M014 Wear head protection&#124;1=M015 Wear high-visibility clothing&#124;2=P004 No thoroughfare&#124;3=W011 Slippery surface |
| `SAFETY_SIGN_AGNOSTIC_NMS` | boolean | false | false |
<!-- END GENERATED -->
