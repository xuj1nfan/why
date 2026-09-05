"""Diagnosis orchestration: retrieve, build context, and ask the LLM."""

from __future__ import annotations

from .context import build_context
from .db import ShellMemory
from .llm import LLMClient
from .models import ShellEvent
from .retrieval import get_diagnosis_events
from .system import collect_system_context


class DiagnosisError(ValueError):
    """The requested diagnosis context cannot be selected."""


def prepare_diagnosis_context(
    memory: ShellMemory,
    session_id: str,
    question: str | None = None,
    limit: int = 15,
    event_id: int | None = None,
    error_output: str | None = None,
) -> tuple[ShellEvent | None, str]:
    if limit < 1:
        raise DiagnosisError("limit must be at least 1")
    if event_id is not None:
        selected_event = memory.get_event(session_id, event_id)
        if selected_event is None:
            raise DiagnosisError(f"event {event_id} was not found in the current session")
        events = memory.get_events_until(session_id, event_id, limit=limit)
    elif question is None:
        selected_event, events = get_diagnosis_events(memory, session_id, limit=limit)
    else:
        selected_event = None
        events = memory.get_recent_events(session_id, limit=limit)

    prompt = build_context(
        events,
        collect_system_context(),
        question=question,
        error_output=error_output,
        selected_event_id=event_id,
    )
    return selected_event, prompt


def diagnose(
    memory: ShellMemory,
    session_id: str,
    llm: LLMClient,
    question: str | None = None,
    limit: int = 15,
    event_id: int | None = None,
    error_output: str | None = None,
) -> str:
    selected_event, prompt = prepare_diagnosis_context(
        memory,
        session_id,
        question=question,
        limit=limit,
        event_id=event_id,
        error_output=error_output,
    )
    if selected_event is None and question is None and event_id is None and not error_output:
        return "No failed shell command found in the current session."
    return llm.complete(prompt)
