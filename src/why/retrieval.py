"""Small, recency-based retrieval helpers for shell memory."""

from __future__ import annotations

from .db import ShellMemory
from .models import ShellEvent


def get_diagnosis_events(
    memory: ShellMemory,
    session_id: str,
    limit: int = 15,
) -> tuple[ShellEvent | None, list[ShellEvent]]:
    """Return the latest failure and events leading up to that failure."""

    if limit < 1:
        return None, []

    failed_event = memory.get_latest_failed_event(session_id)
    if failed_event is None:
        return None, memory.get_recent_events(session_id, limit=limit)

    return failed_event, memory.get_events_until(session_id, failed_event.id, limit=limit)
