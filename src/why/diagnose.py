"""Diagnosis orchestration: retrieve, build context, and ask the LLM."""

from __future__ import annotations

from .context import build_context
from .db import ShellMemory
from .llm import LLMClient
from .retrieval import get_diagnosis_events
from .system import collect_system_context


def diagnose(
    memory: ShellMemory,
    session_id: str,
    llm: LLMClient,
    question: str | None = None,
    limit: int = 15,
) -> str:
    failed_event, events = get_diagnosis_events(memory, session_id, limit=limit)
    if failed_event is None and question is None:
        return "No failed shell command found in the current session."
    prompt = build_context(events, collect_system_context(), question=question)
    return llm.complete(prompt)
