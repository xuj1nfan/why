"""Data models used by the shell memory layer."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Session:
    id: str
    started_at: float


@dataclass(frozen=True)
class ShellEvent:
    id: int
    session_id: str
    command_raw: str
    cwd_before: str
    cwd_after: str | None
    started_at: float
    ended_at: float | None
    exit_code: int | None

    @property
    def duration(self) -> float | None:
        """Return elapsed seconds when the event has been completed."""

        if self.ended_at is None:
            return None
        return max(0.0, self.ended_at - self.started_at)
