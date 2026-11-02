"""Generate the Markdown API reference from OpenAPI without starting the application."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import tempfile
import sys
from unittest.mock import patch

from backend.app.core.config import Settings
from backend.app.core import config
from backend.scripts._doc_utils import ROOT, generated_document, generated_section, parser, publish


def openapi_schema() -> dict:
    # Bind route dependencies to the real, zero-argument get_settings function
    # before isolating main's eager app creation. Dependency bodies are not run
    # by OpenAPI generation. Patching before router import corrupts signatures.
    importlib.import_module("backend.app.api.router")
    # model_construct bypasses BaseSettings sources, including .env and os.environ.
    with tempfile.TemporaryDirectory(prefix="labeling-doc-api-") as directory:
        settings = Settings.model_construct()
        for name in Settings.model_fields:
            if isinstance(getattr(settings, name), Path):
                setattr(settings, name, Path(directory) / name)
        # main creates its module-level app on first import. Isolate that too.
        already_loaded = "backend.app.main" in sys.modules
        original = config.get_settings
        with patch("backend.app.core.config.get_settings", new=lambda: settings):
            module = importlib.import_module("backend.app.main")
        if not already_loaded:
            module.get_settings = original
        with patch.object(module, "get_settings", new=lambda: settings):
            return module.create_app().openapi()


def render(root: Path = ROOT) -> dict[Path, str]:
    schema = openapi_schema()
    lines = []
    for path, item in sorted(schema["paths"].items()):
        for method, operation in sorted(item.items()):
            if method not in {"get", "put", "post", "delete", "patch", "options", "head", "trace"}:
                continue
            lines.extend([f"## {method.upper()} `{path}`", "", operation.get("summary", ""), ""])
            if operation.get("description"):
                lines.extend([operation["description"], ""])
            details = {key: operation[key] for key in ("parameters", "requestBody", "responses", "security") if key in operation}
            lines.extend(["```json", json.dumps(details, indent=2, sort_keys=True, ensure_ascii=False), "```", ""])
    lines.extend(["## Shared components", "", "```json", json.dumps(schema.get("components", {}), indent=2, sort_keys=True, ensure_ascii=False), "```", ""])
    path = root / "docs/API.md"
    intro = """# API reference

Generated from `create_app().openapi()` without requests, worker startup or model
loading. The schema is used in memory; no OpenAPI JSON file is published.
Only declared parameters, bodies and responses are listed; runtime errors can
include additional cases. See [operations](OPERATIONS.md) for partial-operation
errors. The application currently has no API authentication; CORS is not access
control. Restrict access to a trusted local environment.

Regenerate with `uv run python -m backend.scripts.generate_docs`.
"""
    return {
        path: generated_document(path, generated_section(path, intro, "\n".join(lines)).replace(
                                     "](operations.md)", "](OPERATIONS.md)"),
                                 ["backend/app/main.py", "backend/app/api/"], root),
    }


def main() -> int:
    args = parser(__doc__).parse_args()
    return publish(render(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
