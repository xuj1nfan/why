"""Recorder-facing operations used by the internal CLI."""

from __future__ import annotations

import time

from .db import ShellMemory


def begin_event(
    memory: ShellMemory,
    session_id: str,
    command_raw: str,
    cwd_before: str,
) -> int:
    return memory.begin_event(
        session_id=session_id,
        command_raw=command_raw,
        cwd_before=cwd_before,
        started_at=time.time(),
    )


def end_event(
    memory: ShellMemory,
    event_id: int,
    exit_code: int,
    cwd_after: str,
) -> None:
    memory.end_event(
        event_id=event_id,
        exit_code=exit_code,
        cwd_after=cwd_after,
        ended_at=time.time(),
    )


def record_event(
    memory: ShellMemory,
    session_id: str,
    command_raw: str,
    cwd_before: str,
    cwd_after: str,
    started_at: float,
    exit_code: int,
    *,
    retention_days: int | None = None,
    max_events_per_session: int | None = None,
) -> int:
    return memory.record_event(
        session_id=session_id,
        command_raw=command_raw,
        cwd_before=cwd_before,
        cwd_after=cwd_after,
        started_at=started_at,
        ended_at=time.time(),
        exit_code=exit_code,
        retention_days=retention_days,
        max_events_per_session=max_events_per_session,
    )
