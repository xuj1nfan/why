"""SQLite-backed shell memory."""

from __future__ import annotations

import os
import sqlite3
import time
from contextlib import contextmanager
from pathlib import Path
from collections.abc import Iterator
from typing import Iterable

from .models import Session, ShellEvent
from .redaction import redact_command


SCHEMA_VERSION = 2
MIGRATIONS = {
    1: """
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
    """,
    2: """
        CREATE INDEX IF NOT EXISTS idx_shell_events_session_ended
            ON shell_events(session_id, ended_at DESC, id DESC);
        PRAGMA journal_mode = WAL;
    """,
}


class DatabaseVersionError(ValueError):
    """The database was created by a newer, incompatible version of why."""


class ShellMemory:
    """Small repository around the SQLite schema.

    A connection is opened per operation. This keeps CLI invocations
    independent and makes an interrupted shell command unable to hold a
    database connection open.
    """

    def __init__(self, path: str | Path):
        self.path = Path(path).expanduser()

    def _connect(self) -> sqlite3.Connection:
        parent_existed = self.path.parent.exists()
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if not parent_existed:
            self.path.parent.chmod(0o700)

        try:
            descriptor = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600)
        except FileExistsError:
            self.path.chmod(0o600)
        else:
            os.close(descriptor)

        connection = sqlite3.connect(self.path, timeout=2.0)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute("PRAGMA busy_timeout = 2000")
        self._migrate(connection)
        return connection

    @staticmethod
    def _migrate(connection: sqlite3.Connection) -> None:
        version = int(connection.execute("PRAGMA user_version").fetchone()[0])
        if version > SCHEMA_VERSION:
            raise DatabaseVersionError(
                f"database schema {version} is newer than supported version {SCHEMA_VERSION}"
            )
        for target_version in range(version + 1, SCHEMA_VERSION + 1):
            connection.executescript(MIGRATIONS[target_version])
            connection.execute(f"PRAGMA user_version = {target_version}")

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
                (session_id, redact_command(command_raw), cwd_before, started_at),
            )
            return int(cursor.lastrowid)

    def record_event(
        self,
        session_id: str,
        command_raw: str,
        cwd_before: str,
        cwd_after: str,
        started_at: float,
        ended_at: float,
        exit_code: int,
        *,
        retention_days: int | None = None,
        max_events_per_session: int | None = None,
    ) -> int:
        """Atomically store one completed event."""

        if not session_id:
            raise ValueError("session_id must not be empty")
        if not command_raw:
            raise ValueError("command_raw must not be empty")
        if not cwd_before or not cwd_after:
            raise ValueError("event directories must not be empty")
        if retention_days is not None and retention_days < 0:
            raise ValueError("retention_days must be non-negative")
        if max_events_per_session is not None and max_events_per_session < 0:
            raise ValueError("max_events_per_session must be non-negative")

        with self._connection() as connection:
            connection.execute(
                "INSERT OR IGNORE INTO sessions (id, started_at) VALUES (?, ?)",
                (session_id, started_at),
            )
            cursor = connection.execute(
                """INSERT INTO shell_events
                   (session_id, command_raw, cwd_before, cwd_after,
                    started_at, ended_at, exit_code)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    redact_command(command_raw),
                    cwd_before,
                    cwd_after,
                    started_at,
                    ended_at,
                    exit_code,
                ),
            )
            event_id = int(cursor.lastrowid)
            if retention_days is not None or max_events_per_session is not None:
                self._prune_connection(
                    connection,
                    retention_days or 0,
                    max_events_per_session or 0,
                    session_id=session_id,
                    now=ended_at,
                )
            return event_id

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

    def get_event(self, session_id: str, event_id: int) -> ShellEvent | None:
        with self._connection() as connection:
            row = connection.execute(
                """SELECT id, session_id, command_raw, cwd_before, cwd_after,
                          started_at, ended_at, exit_code
                   FROM shell_events
                   WHERE session_id = ? AND id = ?""",
                (session_id, event_id),
            ).fetchone()
        return self._event(row) if row else None

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

    def prune(
        self,
        retention_days: int = 30,
        max_events_per_session: int = 5000,
        *,
        session_id: str | None = None,
        now: float | None = None,
    ) -> int:
        """Delete events outside the age/count policy; zero disables a limit."""

        if retention_days < 0 or max_events_per_session < 0:
            raise ValueError("retention limits must be non-negative")
        with self._connection() as connection:
            return self._prune_connection(
                connection,
                retention_days,
                max_events_per_session,
                session_id=session_id,
                now=time.time() if now is None else now,
            )

    @staticmethod
    def _prune_connection(
        connection: sqlite3.Connection,
        retention_days: int,
        max_events_per_session: int,
        *,
        session_id: str | None,
        now: float,
    ) -> int:
        deleted = 0
        session_filter = " AND session_id = ?" if session_id else ""
        parameters: tuple[object, ...] = (session_id,) if session_id else ()
        if retention_days:
            cutoff = now - retention_days * 86400
            cursor = connection.execute(
                "DELETE FROM shell_events WHERE started_at < ?" + session_filter,
                (cutoff, *parameters),
            )
            deleted += cursor.rowcount

        if max_events_per_session:
            if session_id:
                session_ids = [session_id]
            else:
                session_ids = [
                    row[0] for row in connection.execute("SELECT id FROM sessions").fetchall()
                ]
            for current_session in session_ids:
                cursor = connection.execute(
                    """DELETE FROM shell_events WHERE id IN (
                           SELECT id FROM shell_events
                           WHERE session_id = ?
                           ORDER BY started_at DESC, id DESC
                           LIMIT -1 OFFSET ?
                       )""",
                    (current_session, max_events_per_session),
                )
                deleted += cursor.rowcount

        if session_id:
            connection.execute(
                """DELETE FROM sessions
                   WHERE id = ? AND NOT EXISTS (
                       SELECT 1 FROM shell_events
                       WHERE shell_events.session_id = sessions.id
                   )""",
                (session_id,),
            )
        else:
            connection.execute(
                """DELETE FROM sessions
                   WHERE NOT EXISTS (
                       SELECT 1 FROM shell_events
                       WHERE shell_events.session_id = sessions.id
                   )"""
            )
        return deleted

    def all_sessions(self) -> Iterable[Session]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id, started_at FROM sessions ORDER BY started_at"
            ).fetchall()
        return [self._session(row) for row in rows]
