# PPE Labeling Tool

This project is a local annotation tool for smart factory safety monitoring datasets. It helps review and edit YOLO-format object detection labels for:

- `0`: Human
- `1`: Helmet
- `2`: Vest

The backend can auto-label images with a YOLO model and a vest color detector, while the frontend provides an interactive canvas for editing bounding boxes.

## Project Structure

```text
backend/                 FastAPI backend
  app/api/               API controllers
  app/core/              Runtime configuration
  app/ml/                YOLO inference and vest fallback code
  app/models/            Application request/response schemas
  app/services/          Label, image, visualization, and orchestration services
frontend/                React + Vite annotation UI
data/images/             Local input images, ignored by Git
data/labels/             Local YOLO labels, ignored by Git
data/labeled_images/     Local visualization output, ignored by Git
weights/                 Local deep learning model weights, ignored by Git
```

Generated dependencies, datasets, labels, visualization outputs, `.env`, and model weights are intentionally ignored by Git.

## Prerequisites

- `uv`
- Node.js LTS
- Git

Install `uv` on Windows PowerShell if needed:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

## Backend Setup

Run these commands from the repository root.

### 1. Install Python 3.12

This repo pins Python to `3.12` in `.python-version` and `pyproject.toml`.

```powershell
uv python install 3.12
```

### 2. Sync Python packages

Use uv's normal project workflow. This creates and manages the project environment automatically.

```powershell
uv sync
```

Do not activate `.venv` manually. Run backend commands through `uv run`.

### 3. Configure environment variables

Copy the example environment file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` if needed:

```text
MODEL_PATH=weights/best.pt
IMAGE_DIR=data/images
LABEL_DIR=data/labels
VISUALIZATION_DIR=data/labeled_images
CORS_ORIGINS=http://localhost:5173
YOLO_IMG_SIZE=640
YOLO_CONF=0.25
YOLO_IOU=0.7
USE_COLOR_VEST_FALLBACK=false
```

Place your deep learning model weights at the configured `MODEL_PATH`, for example:

```text
weights/best.pt
```

Place images to annotate in:

```text
data/images/
```

Inference settings:

- `YOLO_IMG_SIZE` should match the image size you used during model validation when you want similar boxes.
- `YOLO_CONF` controls minimum detection confidence.
- `YOLO_IOU` controls non-maximum suppression overlap.
- `USE_COLOR_VEST_FALLBACK=false` means vest boxes come from YOLO class `2`. Set it to `true` only if you want the old HSV color fallback when YOLO finds no vest.

## Frontend Setup

Run these commands from the repository root:

```powershell
cd frontend
npm install
```

## Run The Application

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

## API

The frontend uses these backend endpoints:

- `GET /api/v1/images`
- `DELETE /api/v1/images/{filename}`
- `GET /api/v1/images/{filename}/labels`
- `PUT /api/v1/images/{filename}/labels`
- `POST /api/v1/images/{filename}/auto-label`
- `POST /api/v1/auto-label`
- `POST /api/v1/visualizations`

Images are served from `/media/images/{filename}`.
Generated visualization images are served from `/media/visualizations/{filename}`.

## Development Checks

Backend smoke check:

```powershell
uv run pytest
```

Frontend build check:

```powershell
cd frontend
npm run build
```

Git hygiene check:

```powershell
git ls-files | Select-String "node_modules|\\.pt$|^data/images/|^data/labels/|^data/labeled_images/"
```

The command should not show generated dependencies, model weights, or dataset files.

## Troubleshooting

- Missing model file: make sure `.env` points to an existing `.pt` file.
- Frontend cannot reach backend: confirm the backend is running on port `8000` and the frontend is running on port `5173`.
- No images show up: put `.jpg`, `.jpeg`, or `.png` files in `data/images/`.
- Python version mismatch: run `uv python install 3.12` and `uv sync`.
- Python package errors: rerun `uv sync`.
