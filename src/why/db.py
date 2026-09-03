"""SQLite-backed shell memory."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator
from typing import Iterable

from .models import Session, ShellEvent


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    started_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS shell_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    command_raw TEXT NOT NULL,
    cwd_before TEXT NOT NULL,
    cwd_after TEXT,
    started_at REAL NOT NULL,
    ended_at REAL,
    exit_code INTEGER,
    FOREIGN KEY(session_id) REFERENCES sessions(id)
);

CREATE INDEX IF NOT EXISTS idx_shell_events_session_started
    ON shell_events(session_id, started_at DESC, id DESC);
"""


class ShellMemory:
    """Small repository around the SQLite schema.

    A connection is opened per operation. This keeps CLI invocations
    independent and makes an interrupted shell command unable to hold a
    database connection open.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        connection = self._connect()
        try:
            yield connection
        except Exception:
            connection.rollback()
            raise
        else:
            connection.commit()
        finally:
            connection.close()

    @staticmethod
    def _session(row: sqlite3.Row) -> Session:
        return Session(id=row["id"], started_at=row["started_at"])

    @staticmethod
    def _event(row: sqlite3.Row) -> ShellEvent:
        return ShellEvent(
            id=row["id"],
            session_id=row["session_id"],
            command_raw=row["command_raw"],
            cwd_before=row["cwd_before"],
            cwd_after=row["cwd_after"],
            started_at=row["started_at"],
            ended_at=row["ended_at"],
            exit_code=row["exit_code"],
        )

    def create_session(self, session_id: str, started_at: float) -> Session:
        if not session_id:
            raise ValueError("session_id must not be empty")

        with self._connection() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO sessions (id, started_at) VALUES (?, ?)",
                (session_id, started_at),
            )
            row = connection.execute(
                "SELECT id, started_at FROM sessions WHERE id = ?", (session_id,)
            ).fetchone()
        return self._session(row)

    def begin_event(
        self,
        session_id: str,
        command_raw: str,
        cwd_before: str,
        started_at: float,
    ) -> int:
        if not session_id:
            raise ValueError("session_id must not be empty")
        if not command_raw:
            raise ValueError("command_raw must not be empty")
        if not cwd_before:
            raise ValueError("cwd_before must not be empty")

        with self._connection() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO sessions (id, started_at) VALUES (?, ?)",
                (session_id, started_at),
            )
            cursor = connection.execute(
                """INSERT INTO shell_events
                   (session_id, command_raw, cwd_before, started_at)
                   VALUES (?, ?, ?, ?)""",
                (session_id, command_raw, cwd_before, started_at),
            )
            return int(cursor.lastrowid)

    def end_event(
        self,
        event_id: int,
        exit_code: int,
        cwd_after: str,
        ended_at: float,
    ) -> None:
        if not cwd_after:
            raise ValueError("cwd_after must not be empty")

        with self._connection() as connection:
            cursor = connection.execute(
                """UPDATE shell_events
                   SET cwd_after = ?, ended_at = ?, exit_code = ?
                   WHERE id = ? AND ended_at IS NULL""",
                (cwd_after, ended_at, exit_code, event_id),
            )
            if cursor.rowcount == 0:
                raise ValueError(f"event {event_id} does not exist or is already complete")

    def get_recent_events(self, session_id: str, limit: int = 15) -> list[ShellEvent]:
        if limit < 1:
            return []

        with self._connection() as connection:
            rows = connection.execute(
                """SELECT id, session_id, command_raw, cwd_before, cwd_after,
                          started_at, ended_at, exit_code
                   FROM shell_events
                   WHERE session_id = ?
                   ORDER BY started_at DESC, id DESC
                   LIMIT ?""",
                (session_id, limit),
            ).fetchall()
        return [self._event(row) for row in reversed(rows)]

    def get_events_until(
        self,
        session_id: str,
        event_id: int,
        limit: int = 15,
    ) -> list[ShellEvent]:
        """Return up to *limit* events ending at a specific event."""

        if limit < 1:
            return []

        with self._connection() as connection:
            rows = connection.execute(
                """SELECT id, session_id, command_raw, cwd_before, cwd_after,
                          started_at, ended_at, exit_code
                   FROM shell_events
                   WHERE session_id = ? AND id <= ?
                   ORDER BY id DESC
                   LIMIT ?""",
                (session_id, event_id, limit),
            ).fetchall()
        return [self._event(row) for row in reversed(rows)]

    def get_latest_failed_event(self, session_id: str) -> ShellEvent | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT id, session_id, command_raw, cwd_before, cwd_after,
                          started_at, ended_at, exit_code
                   FROM shell_events
                   WHERE session_id = ? AND exit_code IS NOT NULL AND exit_code != 0
                   ORDER BY ended_at DESC, id DESC
                   LIMIT 1""",
                (session_id,),
            ).fetchone()
        return self._event(row) if row else None

    def clear(self, session_id: str | None = None) -> int:
        with self._connection() as connection:
            if session_id is None:
                cursor = connection.execute("DELETE FROM shell_events")
                connection.execute("DELETE FROM sessions")
            else:
                cursor = connection.execute(
                    "DELETE FROM shell_events WHERE session_id = ?", (session_id,)
                )
                connection.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            return cursor.rowcount

    def all_sessions(self) -> Iterable[Session]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, started_at FROM sessions ORDER BY started_at"
            ).fetchall()
        return [self._session(row) for row in rows]
