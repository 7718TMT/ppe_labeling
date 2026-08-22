"""Start the complete local labeling product with one command.

Run from the repository root with::

    uv run python -m backend.scripts.start_app

The launcher owns only process lifecycle. Application behavior remains in the
FastAPI application, the persistent video worker, and the React/Vite frontend.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


POLL_INTERVAL_SECONDS = 0.25
SHUTDOWN_TIMEOUT_SECONDS = 5.0


@dataclass(frozen=True)
class ServiceSpec:
    """Describe one long-running application service."""

    name: str
    command: tuple[str, ...]
    cwd: Path


@dataclass
class RunningService:
    """Associate a service description with its child process."""

    spec: ServiceSpec
    process: subprocess.Popen[bytes]


def repository_root() -> Path:
    """Return the repository root independently of the caller's directory."""

    return Path(__file__).resolve().parents[2]


def build_service_specs(
    root: Path | None = None,
    npm_executable: str | None = None,
) -> tuple[ServiceSpec, ...]:
    """Build commands for the API, worker, and frontend services."""

    root = (root or repository_root()).resolve()
    frontend_root = root / "frontend"
    npm = npm_executable or shutil.which("npm")
    if not npm:
        raise RuntimeError(
            "npm was not found. Install Node.js and run npm install in the "
            "frontend directory before starting the application."
        )
    if not frontend_root.is_dir():
        raise RuntimeError(f"Frontend directory was not found: {frontend_root}")

    python = sys.executable
    return (
        ServiceSpec(
            name="API",
            command=(
                python,
                "-m",
                "uvicorn",
                "backend.app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                "8000",
            ),
            cwd=root,
        ),
        ServiceSpec(
            name="video worker",
            command=(python, "-m", "backend.scripts.video_worker"),
            cwd=root,
        ),
        ServiceSpec(
            name="frontend",
            command=(
                npm,
                "run",
                "dev",
                "--",
                "--host",
                "0.0.0.0",
                "--port",
                "5173",
                "--strictPort",
            ),
            cwd=frontend_root,
        ),
    )


def _process_group_options() -> dict[str, int | bool]:
    """Return platform-specific options for an independently managed group."""

    if os.name == "nt":
        return {
            "creationflags": getattr(
                subprocess,
                "CREATE_NEW_PROCESS_GROUP",
                0,
            )
        }
    return {"start_new_session": True}


def start_service(spec: ServiceSpec) -> RunningService:
    """Start one service in its own process group."""

    process = subprocess.Popen(
        list(spec.command),
        cwd=spec.cwd,
        **_process_group_options(),
    )
    return RunningService(spec=spec, process=process)


def monitor_services(
    services: Sequence[RunningService],
    poll_interval: float = POLL_INTERVAL_SECONDS,
) -> int:
    """Wait until a required service exits and propagate a useful exit code."""

    while True:
        for service in services:
            return_code = service.process.poll()
            if return_code is None:
                continue
            if return_code == 0:
                print(
                    f"{service.spec.name} stopped unexpectedly.",
                    file=sys.stderr,
                )
                return 1
            print(
                f"{service.spec.name} failed with exit code {return_code}.",
                file=sys.stderr,
            )
            return return_code if return_code > 0 else 1
        time.sleep(poll_interval)


def _request_stop(process: subprocess.Popen[bytes]) -> None:
    """Ask a child process group to stop, with a direct-process fallback."""

    if process.poll() is not None:
        return
    try:
        if os.name == "nt":
            process.send_signal(getattr(signal, "CTRL_BREAK_EVENT"))
        else:
            os.killpg(process.pid, signal.SIGTERM)
    except (AttributeError, OSError, ProcessLookupError):
        try:
            process.terminate()
        except OSError:
            pass


def _force_stop(process: subprocess.Popen[bytes]) -> None:
    """Force-stop a child process group after graceful shutdown times out."""

    if process.poll() is not None:
        return
    if os.name == "nt":
        try:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            return
        except OSError:
            pass
    else:
        try:
            os.killpg(process.pid, signal.SIGKILL)
            return
        except (OSError, ProcessLookupError):
            pass
    try:
        process.kill()
    except OSError:
        pass


def shutdown_services(
    services: Sequence[RunningService],
    timeout: float = SHUTDOWN_TIMEOUT_SECONDS,
) -> None:
    """Stop all children gracefully, then force-stop any remaining groups."""

    for service in services:
        _request_stop(service.process)

    deadline = time.monotonic() + timeout
    for service in services:
        remaining = max(0.0, deadline - time.monotonic())
        try:
            service.process.wait(timeout=remaining)
        except subprocess.TimeoutExpired:
            pass

    for service in services:
        _force_stop(service.process)

    # Reap force-stopped children so the launcher never leaves zombie process
    # handles behind. A final direct kill covers an unusually slow group stop.
    for service in services:
        if service.process.poll() is not None:
            continue
        try:
            service.process.wait(timeout=1.0)
        except subprocess.TimeoutExpired:
            try:
                service.process.kill()
                service.process.wait(timeout=1.0)
            except (OSError, subprocess.TimeoutExpired):
                pass


def run() -> int:
    """Run all product services until interrupted or one service fails."""

    services: list[RunningService] = []
    try:
        specs = build_service_specs()
        for spec in specs:
            print(f"Starting {spec.name}...")
            services.append(start_service(spec))
        print("Labeling product is available at http://localhost:5173")
        return monitor_services(services)
    except KeyboardInterrupt:
        print("\nStopping labeling product...")
        return 130
    except (OSError, RuntimeError) as exc:
        print(f"Could not start the labeling product: {exc}", file=sys.stderr)
        return 1
    finally:
        shutdown_services(services)


def main() -> None:
    """CLI entry point."""

    raise SystemExit(run())


if __name__ == "__main__":
    main()
