# Smart Factory Annotation Tool

This repository contains a local image annotation tool for smart factory safety monitoring datasets. It combines a FastAPI backend, a React/Vite frontend, task-specific auto-labeling, and manual review/editing of YOLO-format bounding boxes.

The app is organized around annotation tasks. Each task has its own images, labels, visualization output, model settings, and class mapping so datasets do not overlap.

## Supported Tasks

### PPE

The PPE task is for annotating worker safety equipment.

Classes:

- `0`: Person
- `1`: Helmet
- `2`: Vest

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
  app/api/                        API and media routes
  app/core/                       Settings and task profiles
  app/ml/                         Auto-labeling model integrations
  app/models/                     Request/response schemas
  app/services/                   Label, image, visualization, and orchestration logic
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

Create your local environment file:

```powershell
Copy-Item .env.example .env
```

Important settings:

```text
ACTIVE_TASK=safety_signs
CORS_ORIGINS=http://localhost:5173

PPE_MODEL_PATH=weights/ppe.pt
PPE_IMAGE_DIR=data/ppe/images
PPE_LABEL_DIR=data/ppe/labels
PPE_VISUALIZATION_DIR=data/ppe/labeled_images

SAFETY_SIGN_MODEL_PATH=weights/sign.pt
SAFETY_SIGN_IMAGE_DIR=data/safety_signs/images
SAFETY_SIGN_LABEL_DIR=data/safety_signs/labels
SAFETY_SIGN_VISUALIZATION_DIR=data/safety_signs/labeled_images
SAFETY_SIGN_CONF=0.15
SAFETY_SIGN_IMG_SIZE=640
SAFETY_SIGN_IOU=0.7
SAFETY_SIGN_AGNOSTIC_NMS=false
```

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

## API Overview

Task-scoped endpoints:

- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{task}/images`
- `DELETE /api/v1/tasks/{task}/images/{filename}`
- `GET /api/v1/tasks/{task}/images/{filename}/labels`
- `PUT /api/v1/tasks/{task}/images/{filename}/labels`
- `POST /api/v1/tasks/{task}/images/{filename}/auto-label`
- `POST /api/v1/tasks/{task}/auto-label`
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

Git hygiene check:

```powershell
git ls-files | Select-String "node_modules|\\.pt$|^data/ppe/images/|^data/ppe/labels/|^data/ppe/labeled_images/|^data/safety_signs/images/|^data/safety_signs/labels/|^data/safety_signs/labeled_images/"
```

The command should not show generated dependencies, model weights, or dataset files except `.gitkeep` placeholders.

## Troubleshooting

- Missing model file: check the task-specific model path in `.env`.
- Sign detector class mismatch: make sure `SAFETY_SIGN_MODEL_PATH` points to a trained sign detector whose class IDs are `0-3`.
- No images show up: put images in the selected task image folder.
- Wrong task data appears: confirm the selected task in the UI and the task-specific paths in `.env`.
- Frontend cannot reach backend: confirm backend port `8000`, frontend port `5173`, and `CORS_ORIGINS`.
- Python version mismatch: run `uv python install 3.12` and `uv sync`.
- Python package errors: rerun `uv sync`.
