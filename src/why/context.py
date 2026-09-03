"""Build the transparent prompt/context preview sent to a future LLM."""

from __future__ import annotations

from .models import ShellEvent
from .system import SystemContext


def _format_exit_code(exit_code: int | None) -> str:
    return "incomplete" if exit_code is None else str(exit_code)


def build_context(
    events: list[ShellEvent],
    system: SystemContext,
    question: str | None = None,
) -> str:
    """Create a structured, secret-free context string."""

    git = system.git
    if git.commit is None:
        git_text = "not a Git repository"
    else:
        state = "dirty" if git.dirty else "clean"
        git_text = f"branch: {git.branch}\ncommit: {git.commit}\nstatus: {state}"

    lines = [
        "You are diagnosing a shell failure.",
        "",
        "Current environment",
        "───────────────────",
        f"OS: {system.os_name}",
        f"Shell: {system.shell}",
        f"Current directory: {system.cwd}",
        "",
        "Git",
        "───────────────────",
        git_text,
        "",
        "Recent shell memory",
        "───────────────────",
    ]

    if events:
        for index, event in enumerate(events, start=1):
            lines.extend(
                [
                    "",
                    f"[{index}]",
                    f"command: {event.command_raw}",
                    f"cwd_before: {event.cwd_before}",
                    f"cwd_after: {event.cwd_after or '(incomplete)'}",
                    f"exit_code: {_format_exit_code(event.exit_code)}",
                ]
            )
    else:
        lines.append("(no shell events recorded for this session)")

    lines.extend(
        [
            "",
            "Task",
            "───────────────────",
            question or "Diagnose the latest failed command.",
            "",
            "Use shell history as causal evidence.",
            "Do not assume commands succeeded when exit_code != 0.",
            "Do not invent error output that is not present.",
            "Clearly distinguish evidence from hypothesis.",
            "",
            "Note: why does not capture stdout/stderr in this version.",
        ]
    )
    return "\n".join(lines)
