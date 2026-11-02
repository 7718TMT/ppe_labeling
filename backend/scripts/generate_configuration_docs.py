"""Generate configuration reference without constructing environment settings."""

from __future__ import annotations

import json
from pathlib import Path

from backend.app.core.config import Settings
from backend.scripts._doc_utils import ROOT, cell, generated_document, generated_section, parser, publish


def render(root: Path = ROOT) -> dict[Path, str]:
    examples = {}
    for line in (root / ".env.example").read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        optional = stripped.startswith("# ")
        if optional:
            stripped = stripped[2:]
        key, separator, value = stripped.partition("=")
        if separator and key.isidentifier() and key.isupper():
            examples[key] = value + (" (commented example)" if optional else "")
    schema = Settings.model_json_schema()["properties"]
    lines = ["| Variable | Type | Code default | .env.example |", "|---|---|---|---|"]
    for name, field in Settings.model_fields.items():
        default = field.get_default(call_default_factory=True)
        if isinstance(default, Path):
            default = default.as_posix()
        entry = schema[name]
        kind = entry.get("type") or " / ".join(item.get("type", str(item)) for item in entry.get("anyOf", []))
        lines.append(f"| `{name.upper()}` | {cell(kind)} | {cell(json.dumps(default, default=str))} | {cell(examples.get(name.upper(), '—'))} |")
    unknown = set(examples) - {name.upper() for name in Settings.model_fields}
    if unknown:
        raise ValueError(f"Unknown .env.example keys: {sorted(unknown)}")
    path = root / "docs/CONFIGURATION.md"
    intro = """# Configuration reference

Run commands from the repository root. Relative paths resolve against that working
directory. Copy `.env.example` to `.env` for local operation; this generator never
reads `.env` or environment overrides. Defaults below come from `Settings`.

Class maps use `ID=Name` separated by `|`. Model outputs must use the same IDs.
Device, tracker, confidence and image-size changes can affect quality; benchmark
before changing them. See [operations](OPERATIONS.md) for execution and storage.

Regenerate with `uv run python -m backend.scripts.generate_docs`.
"""
    content = generated_section(path, intro, "\n".join(lines)).replace(
        "](operations.md)", "](OPERATIONS.md)")
    return {path: generated_document(path, content, ["backend/app/core/config.py", ".env.example"], root)}


def main() -> int:
    args = parser(__doc__).parse_args()
    return publish(render(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
