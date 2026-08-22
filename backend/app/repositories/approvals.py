import logging
import sqlite3
from contextlib import contextmanager
from functools import lru_cache
from pathlib import Path
from typing import Iterator
from uuid import uuid4

from backend.app.domain.errors import ApprovalPersistenceError


logger = logging.getLogger(__name__)


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
    connection: sqlite3.Connection | None = None
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path, timeout=5.0)
        connection.execute("PRAGMA journal_mode = WAL")
        connection.execute("PRAGMA busy_timeout = 5000")
        connection.executescript(SCHEMA)
        connection.commit()
    except (OSError, sqlite3.Error) as exc:
        raise ApprovalPersistenceError("Approval persistence is unavailable") from exc
    finally:
        if connection is not None:
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
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    "SELECT filename FROM approval_status WHERE task_id = ? AND is_approved = 1",
                    (task_id,),
                )
                return {row[0] for row in rows}
        except sqlite3.Error as exc:
            logger.exception("Reading approval metadata failed", extra={"task_id": task_id})
            raise ApprovalPersistenceError("Approval persistence is unavailable") from exc

    def set_approval(self, task_id: str, filename: str, is_approved: bool) -> None:
        if not is_approved:
            self.delete_approval(task_id, filename)
            return

        try:
            with self._connection() as connection, connection:
                connection.execute(
                    """
                    INSERT INTO approval_status (task_id, filename, is_approved)
                    VALUES (?, ?, 1)
                    ON CONFLICT(task_id, filename) DO UPDATE SET
                        is_approved = 1,
                        updated_at = CURRENT_TIMESTAMP
                    """,
                    (task_id, filename),
                )
        except sqlite3.Error as exc:
            logger.exception("Writing approval metadata failed", extra={"task_id": task_id, "image_filename": filename})
            raise ApprovalPersistenceError("Approval persistence is unavailable") from exc

    def delete_approval(self, task_id: str, filename: str) -> None:
        try:
            with self._connection() as connection, connection:
                connection.execute(
                    "DELETE FROM approval_status WHERE task_id = ? AND filename = ?",
                    (task_id, filename),
                )
        except sqlite3.Error as exc:
            logger.exception("Deleting approval metadata failed", extra={"task_id": task_id, "image_filename": filename})
            raise ApprovalPersistenceError("Approval persistence is unavailable") from exc

    def remap_filenames(self, task_id: str, filename_map: dict[str, str]) -> tuple[str, ...]:
        """Rename approval records in one transaction and discard stale rows.

        Rows that do not name a source image cannot be remapped and may collide
        with a target name. They are stale approval metadata because the
        filesystem has already completed the rename when this method is called.
        """
        if not filename_map:
            return ()

        source_names = set(filename_map)
        temporary_prefix = f"__renaming_{uuid4().hex}__"

        try:
            with self._connection() as connection, connection:
                rows = connection.execute(
                    "SELECT filename FROM approval_status WHERE task_id = ? ORDER BY filename",
                    (task_id,),
                ).fetchall()
                stale_filenames = tuple(filename for (filename,) in rows if filename not in source_names)
                connection.executemany(
                    "DELETE FROM approval_status WHERE task_id = ? AND filename = ?",
                    [(task_id, filename) for filename in stale_filenames],
                )

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
            return stale_filenames
        except sqlite3.Error as exc:
            logger.exception("Approval filename remapping failed", extra={"task_id": task_id})
            raise ApprovalPersistenceError("Approval persistence is unavailable") from exc


    def stale_filenames(self, task_id: str, current_filenames: set[str]) -> tuple[str, ...]:
        try:
            with self._connection() as connection:
                rows = connection.execute(
                    "SELECT filename FROM approval_status WHERE task_id = ? ORDER BY filename",
                    (task_id,),
                ).fetchall()
        except sqlite3.Error as exc:
            logger.exception("Reading stale approval metadata failed", extra={"task_id": task_id})
            raise ApprovalPersistenceError("Approval persistence is unavailable") from exc
        return tuple(filename for (filename,) in rows if filename not in current_filenames)

    def delete_filenames(self, task_id: str, filenames: tuple[str, ...]) -> None:
        if not filenames:
            return
        try:
            with self._connection() as connection, connection:
                connection.executemany(
                    "DELETE FROM approval_status WHERE task_id = ? AND filename = ?",
                    [(task_id, filename) for filename in filenames],
                )
        except sqlite3.Error as exc:
            logger.exception("Deleting stale approval metadata failed", extra={"task_id": task_id, "filenames": filenames})
            raise ApprovalPersistenceError("Approval persistence is unavailable") from exc
