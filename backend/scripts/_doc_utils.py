"""Shared deterministic, atomic document publishing helpers."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BEGIN = "<!-- BEGIN GENERATED -->"
END = "<!-- END GENERATED -->"
NOTICE_BEGIN = "<!-- BEGIN GENERATED NOTICE -->"
NOTICE_END = "<!-- END GENERATED NOTICE -->"


def generation_metadata(previous: dict | None, unchanged: bool, root: Path = ROOT) -> dict:
    """Retain the generation date for unchanged output, including across days."""
    try:
        commit = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--short=12", "HEAD"],
            check=True, capture_output=True, text=True,
        ).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        commit = "unavailable"
    date = datetime.now(timezone(timedelta(hours=7))).date().isoformat()
    if unchanged and previous and previous.get("commit") == commit:
        candidate = previous.get("date", "")
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", candidate):
            date = candidate
    return {"date": date, "commit": commit}


def generated_document(path: Path, content: str, sources: list[str], root: Path = ROOT) -> str:
    """Maintain a notice below the title without duplicating it on regeneration."""
    pattern = re.compile(re.escape(NOTICE_BEGIN) + r"\n.*?" + re.escape(NOTICE_END) + r"\n\n", re.DOTALL)
    previous_text = path.read_text(encoding="utf-8") if path.exists() else ""
    previous_notice = pattern.search(previous_text)
    previous = None
    if previous_notice:
        stamp = re.search(r"> Generated (\d{4}-\d{2}-\d{2}) at commit `([^`]+)`", previous_notice.group())
        if stamp:
            previous = {"date": stamp[1], "commit": stamp[2]}
    clean = pattern.sub("", content)
    metadata = generation_metadata(previous, pattern.sub("", previous_text) == clean, root)
    sources_text = ", ".join(f"`{source}`" for source in sources)
    notice = (
        f"{NOTICE_BEGIN}\n"
        "> **Generated file — do not edit by hand.**\n"
        f"> Produced by `backend/scripts/generate_docs.py` from {sources_text}.\n"
        "> Regenerate after changing those sources; edit the generator scripts, not this file.\n"
        "> Run `uv run python -m backend.scripts.generate_docs`.\n"
        ">\n"
        f"> Generated {metadata['date']} at commit `{metadata['commit']}`.\n"
        "> Commit identifies the checkout; output may include uncommitted source changes.\n"
        f"{NOTICE_END}\n\n"
    )
    title, separator, rest = clean.partition("\n\n")
    return title + "\n\n" + notice + rest if separator else clean + "\n\n" + notice


def parser(description: str) -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=description)
    result.add_argument("--check", action="store_true", help="Report drift without writing files")
    return result


def publish(outputs: dict[Path, str], *, check: bool = False) -> int:
    """Render first, then atomically replace each changed file. Clean up on error."""
    changed = []
    for path, content in outputs.items():
        content = content.replace("\r\n", "\n")
        expected = content.encode("utf-8")
        if path.exists() and path.read_bytes() == expected:
            continue
        changed.append(path)
        if check:
            print(f"Out of date: {path}")
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(expected)
            os.replace(temporary, path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
        print(f"Generated: {path}")
    return int(check and bool(changed))


def generated_section(path: Path, introduction: str, body: str) -> str:
    """Preserve prose outside the single generated region; reject malformed markers."""
    original = path.read_text(encoding="utf-8") if path.exists() else introduction + "\n" + BEGIN + "\n" + END + "\n"
    if original.count(BEGIN) != 1 or original.count(END) != 1:
        raise ValueError(f"Expected one generated region in {path}")
    before, rest = original.split(BEGIN)
    _, after = rest.split(END)
    return before + BEGIN + "\n" + body.rstrip() + "\n" + END + after


def cell(value: object) -> str:
    return str(value).replace("|", "&#124;").replace("\n", "<br>")
