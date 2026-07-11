import sqlite3
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator
from uuid import uuid4


SCHEMA = """
CREATE TABLE IF NOT EXISTS approval_status (
    task_id TEXT NOT NULL,
    filename TEXT NOT NULL,
    is_approved INTEGER NOT NULL CHECK (is_approved IN (0, 1)),
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (task_id, filename)
);

"""


@lru_cache
def initialize_database(database_path: str) -> None:
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0)
    try:
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.executescript(SCHEMA)
        connection.commit()
    finally:
        connection.close()


class ApprovalRepository:
    """SQLite persistence for review approval metadata.

    Images and YOLO labels remain filesystem artifacts because they are the
    dataset itself. Approval is application metadata and is stored separately.
    """

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path
        initialize_database(str(database_path))

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(self.database_path, timeout=5.0)
        connection.execute("PRAGMA busy_timeout = 5000")
        try:
            yield connection
        finally:
            connection.close()

    def approved_filenames(self, task_id: str) -> set[str]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT filename FROM approval_status WHERE task_id = ? AND is_approved = 1",
                (task_id,),
            )
            return {row[0] for row in rows}

    def set_approval(self, task_id: str, filename: str, is_approved: bool) -> None:
        with self._connection() as connection, connection:
            connection.execute(
                """
                INSERT INTO approval_status (task_id, filename, is_approved)
                VALUES (?, ?, ?)
                ON CONFLICT(task_id, filename) DO UPDATE SET
                    is_approved = excluded.is_approved,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (task_id, filename, int(is_approved)),
            )

    def delete_approval(self, task_id: str, filename: str) -> None:
        with self._connection() as connection, connection:
            connection.execute(
                "DELETE FROM approval_status WHERE task_id = ? AND filename = ?",
                (task_id, filename),
            )

    def rename_approvals(self, task_id: str, filename_map: dict[str, str]) -> None:
        current_filenames = set(filename_map.values())
        temporary_prefix = f"__renaming_{uuid4().hex}__"

        with self._connection() as connection, connection:
            for source_name in filename_map:
                connection.execute(
                    "UPDATE approval_status SET filename = ? WHERE task_id = ? AND filename = ?",
                    (f"{temporary_prefix}{source_name}", task_id, source_name),
                )

            for source_name, target_name in filename_map.items():
                connection.execute(
                    "UPDATE approval_status SET filename = ? WHERE task_id = ? AND filename = ?",
                    (target_name, task_id, f"{temporary_prefix}{source_name}"),
                )

            rows = connection.execute(
                "SELECT filename FROM approval_status WHERE task_id = ?",
                (task_id,),
            ).fetchall()
            stale_filenames = [(task_id, filename) for (filename,) in rows if filename not in current_filenames]
            connection.executemany(
                "DELETE FROM approval_status WHERE task_id = ? AND filename = ?",
                stale_filenames,
            )
