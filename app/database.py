import sqlite3
import threading
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

from app.errors import AppError


class Database:
    """Short-lived connections; one process, serialized writes and final reads."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.lock = threading.RLock()
        self.on_changed: Callable[[], None] | None = None

    @contextmanager
    def connect(self, write: bool = False) -> Iterator[sqlite3.Connection]:
        if self.path.is_symlink():
            raise AppError(503, "unsafe_storage", "Database storage is not a regular file.")
        conn = sqlite3.connect(self.path, timeout=3, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON")
        conn.execute("PRAGMA secure_delete=ON")
        conn.execute("PRAGMA synchronous=FULL")
        try:
            if write:
                conn.execute("BEGIN IMMEDIATE")
            yield conn
            if write:
                conn.execute("COMMIT")
        except BaseException:
            if conn.in_transaction:
                conn.execute("ROLLBACK")
            raise
        finally:
            conn.close()

    def migrate(self) -> None:
        with self.lock, self.connect() as conn:
            current = conn.execute("PRAGMA user_version").fetchone()[0]
            files = sorted((Path(__file__).parent / "migrations").glob("*.sql"))
            if current > len(files):
                raise AppError(503, "newer_database", "Database schema is newer than this backend.")
            for version, file in enumerate(files, 1):
                if version > current:
                    # executescript starts its own transaction; embed BEGIN/COMMIT for atomic DDL.
                    conn.executescript(
                        "BEGIN IMMEDIATE;\n"
                        + file.read_text()
                        + f"\nPRAGMA user_version={version};\nCOMMIT;"
                    )
        self.path.chmod(0o600)

    @staticmethod
    def generation(conn: sqlite3.Connection) -> int:
        return int(conn.execute("SELECT value FROM meta WHERE key='generation'").fetchone()[0])

    def changed(self, conn: sqlite3.Connection) -> int:
        conn.execute("UPDATE meta SET value=value+1 WHERE key='generation'")
        if self.on_changed is not None:
            self.on_changed()
        return Database.generation(conn)

    def compact(self) -> None:
        with self.lock, self.connect() as conn:
            conn.execute("VACUUM")
