# Smart Factory Annotation Tool

This repository contains a local image annotation tool for smart factory safety monitoring datasets. It combines a FastAPI backend, a React/Vite frontend, task-specific auto-labeling, and manual review/editing of YOLO-format bounding boxes.

The app is organized around annotation tasks. Each task has its own images, labels, visualization output, model settings, and class mapping so datasets do not overlap.

Architecture and operational details are maintained in [docs/architecture.md](docs/architecture.md) and [docs/operations.md](docs/operations.md).

## Supported Tasks

### PPE

The PPE task is for annotating worker safety equipment.

Classes:

- `0`: Person
- `1`: Helmet
- `2`: Vest
- `3`: Cleaning Coverall

Expected local data:

```text
data/ppe/images/
data/ppe/labels/
data/ppe/labeled_images/
```

Expected local weights:

```text
weights/ppe.pt
```

### Safety Signs

The safety-sign task is for annotating selected ISO 7010 factory safety signs. The configured sign detector should be a trained YOLO model whose class IDs match the final ISO class mapping below.

Final reviewed classes:

- `0`: M014 Wear head protection
- `1`: M015 Wear high-visibility clothing
- `2`: P004 No thoroughfare
- `3`: W011 Slippery surface

Auto-label detections are saved directly as classes `0-3`. Manual boxes added with `Add Sign` start as class `0`; use the UI dropdown to reassign them when needed.

Expected local data:

```text
data/safety_signs/images/
data/safety_signs/labels/
data/safety_signs/labeled_images/
```

Expected local weights:

```text
weights/sign.pt
```

## Project Structure

```text
backend/                          FastAPI backend
  app/api/                        Controllers, HTTP schemas, dependencies, and router registration
  app/core/                       Settings, task profiles, and device selection
  app/domain/                     Internal models, errors, and geometry utilities
  app/inference/                  Detector protocol and model integrations
  app/repositories/               Filesystem dataset and SQLite approval persistence
  app/services/                   Annotation, label, visualization, and reconciliation workflows
  scripts/                        Operational maintenance commands
  tests/                          Backend tests
frontend/                         React + Vite annotation UI
  src/api/                        Frontend API client
  src/components/                 Canvas, toolbar, and sidebar components
data/                             Local task data, ignored by Git except .gitkeep files
weights/                          Local model weights, ignored by Git except .gitkeep
pyproject.toml                    Python project and dependency definition
uv.lock                           Locked Python dependency graph
```

Generated dependencies, datasets, labels, visualization outputs, `.env`, and model weights are intentionally ignored by Git.

## Backend Setup

Prerequisites:

- `uv`
- Git

Install `uv` on Windows PowerShell if needed:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

From the repository root:

```powershell
uv python install 3.12
uv sync
```

This repo pins Python to `3.12`. Use `uv run ...` for backend commands; manual `.venv` activation is not required.

On Windows and Linux, `uv sync` installs the PyTorch CUDA 13.2 build from the PyTorch wheel index. The app still runs on CPU when CUDA is not available.

Verify PyTorch and CUDA:

```powershell
uv run python -c "import torch; print(torch.__version__); print(torch.version.cuda); print(torch.cuda.is_available()); print(torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'CPU only')"
```

For GPU inference, this should show a `+cu132` PyTorch build, CUDA `13.2`, and `True` for `torch.cuda.is_available()`.

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Important settings:

```text
CORS_ORIGINS=http://localhost:5173
INFERENCE_DEVICE=auto
DATABASE_PATH=data/labeling_db.sqlite3

PPE_MODEL_PATH=weights/ppe.pt
PPE_IMAGE_DIR=data/ppe/images
PPE_LABEL_DIR=data/ppe/labels
PPE_VISUALIZATION_DIR=data/ppe/labeled_images
PPE_CLASS_NAMES=0=Person|1=Helmet|2=Vest|3=Cleaning Coverall

SAFETY_SIGN_MODEL_PATH=weights/sign.pt
SAFETY_SIGN_IMAGE_DIR=data/safety_signs/images
SAFETY_SIGN_LABEL_DIR=data/safety_signs/labels
SAFETY_SIGN_VISUALIZATION_DIR=data/safety_signs/labeled_images
SAFETY_SIGN_CONF=0.15
SAFETY_SIGN_IMG_SIZE=640
SAFETY_SIGN_IOU=0.7
SAFETY_SIGN_CLASS_NAMES=0=M014 Wear head protection|1=M015 Wear high-visibility clothing|2=P004 No thoroughfare|3=W011 Slippery surface
SAFETY_SIGN_AGNOSTIC_NMS=false
```

Class maps use `ID=Name` entries separated by `|`. To add a class later, update the task's class map and replace the task model with a model trained to output the same class ID. The backend filters auto-label detections to the configured class IDs, the API rejects manual labels outside the task map, and the UI renders the dropdown from the backend task metadata.

Inference device options:

- `INFERENCE_DEVICE=auto`: use `cuda:0` when PyTorch can access CUDA, otherwise CPU.
- `INFERENCE_DEVICE=cpu`: force CPU inference.
- `INFERENCE_DEVICE=cuda`, `cuda:0`, or `0`: request a specific NVIDIA CUDA device.

Approval state is stored in SQLite at `DATABASE_PATH`. Images, YOLO labels, and generated visualizations remain filesystem artifacts because they are the dataset and its derived output.

If upgrading an existing installation that still has task-local
`labels/approved.json`, run the explicit dry-run and apply migration described
in [docs/operations.md](docs/operations.md#release-migration-from-legacy-approvedjson) before relying on SQLite approval state.

## Frontend Setup

Prerequisites:

- Node.js LTS

From the repository root:

```powershell
cd frontend
npm install
```

## Run The App

Start the backend from the repository root:

```powershell
uv run uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Start the frontend in a second terminal:

```powershell
cd frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

## Annotation Workflow

You can add images from the UI with `Upload Images`, or place files directly in the selected task image folder.

Common UI actions:

- `AI Current`: auto-label the selected image.
- `AI All`: auto-label every image in the selected task.
- `Export Current`: download a zip containing the selected image and its matching YOLO label file.
- `Export All`: download a zip containing all images and matching YOLO label files for the selected task.
- `Rename Sequential`: rename the selected task dataset to `image_00000`, `image_00001`, and so on, keeping image and label basenames aligned.

Exports use this structure:

```text
images/
labels/
```

If an image has no label yet, export creates an empty matching `.txt` file.

## API Overview

Task-scoped endpoints:

- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task}/images`
- `POST /api/v1/tasks/{task}/images/upload`
- `DELETE /api/v1/tasks/{task}/images/{filename}`
- `GET /api/v1/tasks/{task}/images/{filename}/labels`
- `PUT /api/v1/tasks/{task}/images/{filename}/labels`
- `PUT /api/v1/tasks/{task}/images/{filename}/approve`
- `GET /api/v1/tasks/{task}/images/{filename}/export`
- `POST /api/v1/tasks/{task}/images/{filename}/auto-label`
- `POST /api/v1/tasks/{task}/auto-label`
- `GET /api/v1/tasks/{task}/export`
- `POST /api/v1/tasks/{task}/rename-sequential`
- `POST /api/v1/tasks/{task}/visualizations`

Media routes:

- `/media/{task}/images/{filename}`
- `/media/{task}/visualizations/{filename}`

## Development Checks

Backend tests:

```powershell
uv run pytest
```

Frontend build:

```powershell
cd frontend
npm run build
```

Frontend tests:

```powershell
cd frontend
npm run test
```

Git hygiene check:

```powershell
git ls-files | Select-String "node_modules|\\.pt$|^data/ppe/images/|^data/ppe/labels/|^data/ppe/labeled_images/|^data/safety_signs/images/|^data/safety_signs/labels/|^data/safety_signs/labeled_images/"
```

The command should not show generated dependencies, model weights, or dataset files except `.gitkeep` placeholders.

## Troubleshooting

- Missing model file: check the task-specific model path in `.env`.
- Model class mismatch: make sure the task model path points to a trained detector whose class IDs match the task's `*_CLASS_NAMES` map.
- No images show up: put images in the selected task image folder.
- Wrong task data appears: confirm the selected task in the UI and the task-specific paths in `.env`.
- Rename or delete reported a partial operation: inspect the task filesystem first, then use `uv run python -m backend.scripts.reconcile_approvals --task <task> --apply` only to remove stale approval metadata.
- CUDA not used: run the PyTorch verification command above. If `torch.version.cuda` is `None`, rerun `uv sync` and make sure the lockfile is current. If `torch.cuda.is_available()` is `False`, update the NVIDIA driver and confirm the GPU is visible to Windows.
- Frontend cannot reach backend: confirm backend port `8000`, frontend port `5173`, and `CORS_ORIGINS`.
- Python version mismatch: run `uv python install 3.12` and `uv sync`.
- Python package errors: rerun `uv sync`.
