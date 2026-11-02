"""Regression tests for isolation, reproducibility and safe doc publication."""

from pathlib import Path
import sqlite3
import tempfile
import subprocess
import sys

import pytest
from pydantic_settings.sources import DotEnvSettingsSource, EnvSettingsSource

from backend.app.core.config import Settings
from backend.scripts import generate_docs
from backend.scripts._doc_utils import BEGIN, END, generated_document, generated_section, publish


ROOT = Path(__file__).resolve().parents[2]


def test_fresh_process_openapi_preserves_real_dependency_signatures():
    code = """
from backend.scripts.generate_api_docs import openapi_schema
from backend.app.core.config import get_settings
schema = openapi_schema()
from backend.app import main
assert main.get_settings is get_settings
assert not get_settings.cache_info().currsize
operation = schema['paths']['/api/v1/behavior-inference']['get']
assert not any(p['name'] in {'args', 'kwargs'} for p in operation.get('parameters', []))
assert 'task' in {p['name'] for p in schema['paths']['/api/v1/tasks/{task}/images']['get']['parameters']}
"""
    result = subprocess.run([sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_references_are_isolated_deterministic_and_check_detects_drift(tmp_path, monkeypatch):
    (tmp_path / ".env.example").write_bytes((ROOT / ".env.example").read_bytes())
    private_env = tmp_path / ".env"
    private_env.write_text("DATABASE_PATH=DO_NOT_USE.sqlite3\n", encoding="utf-8")
    live_db = tmp_path / "live.sqlite3"
    live_db.write_bytes(b"must remain unchanged")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("DATABASE_PATH", str(live_db))
    monkeypatch.setenv("PPE_CLASS_NAMES", "0=PRIVATE_SENTINEL")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))

    def forbidden(*args, **kwargs):
        raise AssertionError("Generator accessed settings sources or live storage")

    monkeypatch.setattr(DotEnvSettingsSource, "__call__", forbidden)
    monkeypatch.setattr(EnvSettingsSource, "__call__", forbidden)
    monkeypatch.setattr(Settings, "ensure_directories", forbidden)
    connect = sqlite3.connect

    def isolated_connect(database, *args, **kwargs):
        database = Path(database).resolve()
        assert database.is_relative_to(tmp_path)
        assert database != live_db
        return connect(database, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", isolated_connect)
    outputs = generate_docs.render(tmp_path)
    assert set(outputs) == {tmp_path / "docs" / name for name in (
        "CONFIGURATION.md", "API.md", "DATABASE.md",
    )}
    assert outputs == generate_docs.render(tmp_path)
    for content in outputs.values():
        assert "**Generated file — do not edit by hand.**" in content
        assert "Produced by `backend/scripts/generate_docs.py`" in content
        assert "at commit `unavailable`" in content
        assert "](OPERATIONS.md)" in content
        assert "](operations.md)" not in content
    assert "PRIVATE_SENTINEL" not in "".join(outputs.values())
    assert not (tmp_path / "DO_NOT_USE.sqlite3").exists()
    assert live_db.read_bytes() == b"must remain unchanged"
    assert private_env.read_text() == "DATABASE_PATH=DO_NOT_USE.sqlite3\n"
    assert publish(outputs, check=True) == 1
    assert not (tmp_path / "docs").exists()
    assert publish(outputs) == 0
    assert not (tmp_path / "docs/openapi.json").exists()
    assert not (tmp_path / "docs/archive").exists()
    assert publish(generate_docs.render(tmp_path), check=True) == 0
    reference = tmp_path / "docs/API.md"
    reference.write_text(reference.read_text(encoding="utf-8") + "\nManual note.\n", encoding="utf-8")
    assert "Manual note." in generate_docs.render(tmp_path)[reference]
    stale_reference = tmp_path / "docs/CONFIGURATION.md"
    stale_reference.write_text(f"{BEGIN}\nstale\n{END}\n", encoding="utf-8")
    assert publish(generate_docs.render(tmp_path), check=True) == 1
    assert "stale" in stale_reference.read_text()
    assert "annotation_derivative_refreshes" in outputs[tmp_path / "docs/DATABASE.md"]


def test_atomic_publish_retains_previous_file_and_cleans_temporary(tmp_path, monkeypatch):
    output = tmp_path / "reference.md"
    output.write_text("previous", encoding="utf-8")

    def fail(*args):
        raise OSError("publication failed")

    monkeypatch.setattr("backend.scripts._doc_utils.os.replace", fail)
    with pytest.raises(OSError, match="publication failed"):
        publish({output: "replacement"})
    assert output.read_text() == "previous"
    assert list(tmp_path.iterdir()) == [output]


def test_generated_notice_retains_date_until_content_or_commit_changes(tmp_path, monkeypatch):
    from datetime import datetime, timezone
    from types import SimpleNamespace
    from backend.scripts import _doc_utils

    class Clock:
        @classmethod
        def now(cls, tz):
            return datetime(2026, 10, 10, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(_doc_utils, "datetime", Clock)
    monkeypatch.setattr(_doc_utils.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="a9b356b\n"))
    path = tmp_path / "CONFIGURATION.md"
    sources = ["backend/app/core/config.py"]
    content = "# Configuration\n\nContent.\n"
    first = generated_document(path, content, sources, tmp_path)
    assert "> Generated 2026-10-10 at commit `a9b356b`." in first
    path.write_text(first, encoding="utf-8")

    class Later:
        @classmethod
        def now(cls, tz):
            return datetime(2026, 10, 11, tzinfo=timezone.utc).astimezone(tz)

    monkeypatch.setattr(_doc_utils, "datetime", Later)
    assert generated_document(path, first, sources, tmp_path) == first
    changed = generated_document(path, first.replace("Content.", "Updated."), sources, tmp_path)
    assert "> Generated 2026-10-11" in changed
    assert changed.count("**Generated file — do not edit by hand.**") == 1
    monkeypatch.setattr(_doc_utils.subprocess, "run", lambda *a, **kw: SimpleNamespace(stdout="newcommit\n"))
    assert "> Generated 2026-10-11 at commit `newcommit`." in generated_document(path, first, sources, tmp_path)


def test_generated_region_preserves_handwritten_prose(tmp_path):
    output = tmp_path / "reference.md"
    output.write_text(f"Before\n{BEGIN}\nold\n{END}\nAfter\n", encoding="utf-8")
    assert generated_section(output, "unused", "new") == f"Before\n{BEGIN}\nnew\n{END}\nAfter\n"
    output.write_text("Missing markers", encoding="utf-8")
    with pytest.raises(ValueError, match="generated region"):
        generated_section(output, "", "new")


