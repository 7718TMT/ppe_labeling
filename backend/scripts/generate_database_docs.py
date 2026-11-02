"""Document the current migrated schema using only a temporary SQLite database."""

from __future__ import annotations

from pathlib import Path
from contextlib import closing
import sqlite3
import tempfile

from backend.app.repositories.approvals import SCHEMA
from backend.app.repositories.video_db import VIDEO_SCHEMA_VERSION, VideoRepository
from backend.scripts._doc_utils import ROOT, cell, generated_document, generated_section, parser, publish


def render(root: Path = ROOT) -> dict[Path, str]:
    lines = [f"Video schema version: **{VIDEO_SCHEMA_VERSION}**.", ""]
    with tempfile.TemporaryDirectory(prefix="labeling-doc-db-") as directory:
        database = Path(directory) / "schema.sqlite3"
        VideoRepository(database)
        with closing(sqlite3.connect(database)) as connection:
            connection.executescript(SCHEMA)
            tables = connection.execute("SELECT name, sql FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name").fetchall()
            for name, sql in tables:
                quoted = '"' + name.replace('"', '""') + '"'
                lines.extend([f"## `{name}`", "", "| Column | Type | NOT NULL | Default | PK position |", "|---|---|---|---|---|"])
                for _, column, kind, required, default, primary in connection.execute(f"PRAGMA table_info({quoted})"):
                    lines.append(f"| {cell(column)} | {cell(kind)} | {bool(required)} | {cell(default)} | {primary} |")
                lines.extend(["", "Table constraints and foreign keys:", "", "```sql", sql + ";", "```", "", "Indexes:", ""])
                indexes = connection.execute(f"PRAGMA index_list({quoted})").fetchall()
                for _, index, unique, origin, partial in sorted(indexes, key=lambda row: row[1]):
                    iq = '"' + index.replace('"', '""') + '"'
                    columns = [row[2] for row in connection.execute(f"PRAGMA index_info({iq})")]
                    lines.append(f"- `{index}`: columns `{columns}`, unique={bool(unique)}, origin={origin}, partial={bool(partial)}")
                    ddl = connection.execute("SELECT sql FROM sqlite_master WHERE type='index' AND name=?", (index,)).fetchone()
                    if ddl and ddl[0]:
                        lines.extend(["", "```sql", ddl[0] + ";", "```", ""])
                lines.append("")
    path = root / "docs/DATABASE.md"
    intro = """# Database and storage reference

SQLite stores image approval state plus video projects, jobs, annotation history,
tracks, windows, model metadata and exports. Image inventory and YOLO text labels
are filesystem data, not database rows. Video media, pose/features and export
payloads also remain on disk. Keep the configured database and storage roots
together when backing up; an export alone cannot restore a workspace.

Image approval stores current state only, with no approval audit history. Video
annotation history is separate. Migrations run when the video repository opens.
The schema below is produced by applying those migrations to a temporary empty
database, never by inspecting your live installation. NOT NULL shows the SQLite
PRAGMA flag; consult table constraints for primary-key semantics.

See [operations](OPERATIONS.md) for backup and migration instructions.
Regenerate with `uv run python -m backend.scripts.generate_docs`.
"""
    content = generated_section(path, intro, "\n".join(lines)).replace(
        "](operations.md)", "](OPERATIONS.md)")
    return {path: generated_document(path, content, [
        "backend/app/repositories/approvals.py", "backend/app/repositories/video_db.py",
    ], root)}


def main() -> int:
    args = parser(__doc__).parse_args()
    return publish(render(), check=args.check)


if __name__ == "__main__":
    raise SystemExit(main())
