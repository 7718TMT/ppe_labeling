# Smart Factory Annotation Tool

Local annotation and inference for PPE images, safety signs and worker-behavior
videos. Built with FastAPI, React/Vite and a persistent video worker.

## What the system does

The tool helps annotators prepare and review safety-monitoring datasets, and
inspect predictions from supplied models.

| Capability | What you can do |
|---|---|
| PPE image labeling | Draw, correct and review boxes for people and protective equipment; use a supplied detector to generate initial labels. |
| Safety-sign image labeling | Annotate configured safety-sign classes manually or with AI assistance. |
| Behavior video labeling | Import and trim videos, process worker poses/tracks, then review and edit per-worker `others`, `running` and `falling` segments. |
| Inference | Upload images/videos to inspect PPE/Sign predictions, or videos to inspect worker behavior predictions, in separate inference workspaces. |
| Dataset export | Export images with YOLO labels, or approved Behavior samples with segment annotations, pose windows and a reproducibility manifest. |

Image work is saved locally; Behavior projects and processing jobs persist across
restarts. AI-generated labels remain editable and need human review before
approval. Image export can include unapproved images; Behavior export includes
only approved videos selected for export.

This is a labeling and model-inspection tool. It does not train models, create
train/validation/test splits, measure model accuracy or provide a live-camera
safety-monitoring dashboard. Exported samples feed a separate training workflow.

For handover, start with the [checklist](docs/handover/CHECKLIST.md).
For annotation, use the [user guide](docs/USER_GUIDE.md).

## Install

Requires Git, [uv](https://docs.astral.sh/uv/getting-started/installation/) and
Node.js LTS. Run commands from the repository root. **All platforms** below means
Windows PowerShell, Linux Bash and macOS Zsh/Bash; OS-specific blocks are labeled.

**All platforms — install backend dependencies:**

```sh
uv python install 3.12
uv sync
```

Create `.env` from the example using your shell:

**Windows PowerShell:**

```powershell
Copy-Item .env.example .env
```

**Linux/macOS — Bash or Zsh:**

```sh
cp .env.example .env
```

**All platforms — install frontend dependencies:**

```sh
cd frontend
npm install
cd ..
```

Python is pinned to 3.12. Use `uv run` for backend commands; no virtual-environment
activation is needed. Windows/Linux select the CUDA 13.2 PyTorch index; inference
falls back to CPU when CUDA is unavailable. The locked macOS PyTorch wheels target
**Apple Silicon, macOS 14+**; this device selector uses CPU on macOS, not MPS.
Intel Mac installation is not covered by the current PyTorch wheels. See
[platform notes](docs/OPERATIONS.md#platform-notes) before installing.

Check the model paths in [configuration](docs/CONFIGURATION.md) and set `.env`.
The current repository tracks model files, but verify their availability
and provenance in the received checkout. Manual image labeling does not require
a detector; AI actions and Behavior processing require their respective models.
For custom paths and defaults, see [configuration](docs/CONFIGURATION.md).

## Run the app

Ports 8000 and 5173 must be free; use the OS-specific
[port checks](docs/OPERATIONS.md#port-checks) if needed. Coordinate occupied ports
with their owner; do not stop unrelated processes.

**All platforms:**

```sh
uv run python -m backend.scripts.start_app
```

Open **http://localhost:5173**. The launcher runs FastAPI, the video worker and
Vite. Keep its terminal open; press **Ctrl+C** there to stop them together.
The API has no authentication: use a trusted local environment.

Next: follow the [user guide](docs/USER_GUIDE.md) to import, label, review and
export data. For startup failures, see [troubleshooting](docs/OPERATIONS.md#troubleshooting).

## Documentation

| Need | Document |
|---|---|
| Label or inspect images/videos | [User guide](docs/USER_GUIDE.md) |
| Hand data to a trainer | [Data export](docs/DATA_EXPORT.md) |
| Configure models, diagnose faults, back up or restore | [Operations](docs/OPERATIONS.md) |
| Understand the system | [Architecture](docs/ARCHITECTURE.md) |
| Review UI design conventions | [Design](docs/DESIGN.md) |
| Look up settings, endpoints or storage schema | [Configuration](docs/CONFIGURATION.md), [API](docs/API.md), [Database](docs/DATABASE.md) |
| Review feature formulas | [Behavior features](docs/FEATURES_FOR_BEHAVIOR_DETECTION.md) |
| Review limitations and usage rights | [Known limitations](docs/KNOWN_LIMITATIONS.md), [Ownership](OWNERSHIP.md) |
| Receive or hand over the tool | [Checklist](docs/handover/CHECKLIST.md) |

## Development

`backend/app/` contains the API, services and repositories; `backend/scripts/`
contains maintenance commands. `frontend/src/` contains the UI. Local data and
`.env` are ignored by Git; model files under `weights/` are currently tracked.
Do not commit private datasets or credentials.

Backend checks, from the repository root (**all platforms**):

```sh
uv run pytest
uv run python -m backend.scripts.generate_docs --check
```

Frontend checks (**all platforms**, starting from the repository root):

```sh
cd frontend
npm run test
npm run build
```

Regenerate reference documents with
`uv run python -m backend.scripts.generate_docs`; edit their generator scripts,
not the generated files. Historical notes live in `docs/archive/`.
