from pathlib import Path
from unittest.mock import Mock

import pytest

from backend.scripts import start_app


def test_build_service_specs_uses_unified_runtime_commands(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "frontend").mkdir()
    monkeypatch.setattr(start_app.sys, "executable", "python-under-uv")

    specs = start_app.build_service_specs(tmp_path, npm_executable="npm-test")

    assert [spec.name for spec in specs] == ["API", "video worker", "frontend"]
    assert specs[0].command[:4] == (
        "python-under-uv",
        "-m",
        "uvicorn",
        "backend.app.main:app",
    )
    assert specs[1].command == (
        "python-under-uv",
        "-m",
        "backend.scripts.video_worker",
    )
    assert specs[2].command[:3] == ("npm-test", "run", "dev")
    assert "--strictPort" in specs[2].command
    assert specs[2].cwd == (tmp_path / "frontend").resolve()


def test_monitor_services_propagates_child_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    healthy = Mock()
    healthy.poll.return_value = None
    failed = Mock()
    failed.poll.return_value = 7
    services = [
        start_app.RunningService(
            start_app.ServiceSpec("API", ("api",), Path.cwd()),
            healthy,
        ),
        start_app.RunningService(
            start_app.ServiceSpec("frontend", ("frontend",), Path.cwd()),
            failed,
        ),
    ]
    sleep = Mock()
    monkeypatch.setattr(start_app.time, "sleep", sleep)

    assert start_app.monitor_services(services) == 7
    sleep.assert_not_called()


def test_run_starts_every_service_and_cleans_up_on_interrupt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = tuple(
        start_app.ServiceSpec(name, (name,), Path.cwd())
        for name in ("API", "video worker", "frontend")
    )
    running = [
        start_app.RunningService(spec, Mock())
        for spec in specs
    ]
    start = Mock(side_effect=running)
    shutdown = Mock()
    monkeypatch.setattr(start_app, "build_service_specs", lambda: specs)
    monkeypatch.setattr(start_app, "start_service", start)
    monkeypatch.setattr(
        start_app,
        "monitor_services",
        Mock(side_effect=KeyboardInterrupt),
    )
    monkeypatch.setattr(start_app, "shutdown_services", shutdown)

    assert start_app.run() == 130
    assert start.call_count == 3
    shutdown.assert_called_once_with(running)


def test_run_cleans_up_started_services_when_startup_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    specs = (
        start_app.ServiceSpec("API", ("api",), Path.cwd()),
        start_app.ServiceSpec("video worker", ("worker",), Path.cwd()),
    )
    api = start_app.RunningService(specs[0], Mock())
    start = Mock(side_effect=[api, OSError("worker failed")])
    shutdown = Mock()
    monkeypatch.setattr(start_app, "build_service_specs", lambda: specs)
    monkeypatch.setattr(start_app, "start_service", start)
    monkeypatch.setattr(start_app, "shutdown_services", shutdown)

    assert start_app.run() == 1
    shutdown.assert_called_once_with([api])


def test_shutdown_requests_stop_before_force_stopping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    process = Mock()
    process.poll.return_value = 0
    service = start_app.RunningService(
        start_app.ServiceSpec("API", ("api",), Path.cwd()),
        process,
    )
    request_stop = Mock()
    force_stop = Mock()
    monkeypatch.setattr(start_app, "_request_stop", request_stop)
    monkeypatch.setattr(start_app, "_force_stop", force_stop)

    start_app.shutdown_services([service], timeout=0.1)

    request_stop.assert_called_once_with(process)
    process.wait.assert_called_once()
    force_stop.assert_called_once_with(process)
