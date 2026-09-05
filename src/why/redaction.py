"""Best-effort removal of credentials from recorded shell commands."""

from __future__ import annotations

import re


REDACTED = "<redacted>"

_SENSITIVE_NAME = (
    r"(?:api[_-]?key|access[_-]?token|token|password|passwd|secret|"
    r"private[_-]?key|client[_-]?secret|authorization|auth|cookie)"
)
_SENSITIVE_OPTION = (
    r"(?:(?:[a-z0-9]+[-_])*(?:api[-_]?key|token|password|passwd|secret|"
    r"private[-_]?key|client[-_]?secret|authorization|cookie)"
    r"(?:[-_][a-z0-9]+)*)"
)
_VALUE = r'''(?:"[^"\n]*"|'[^'\n]*'|[^\s;&|]+)'''

_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            rf"(?i)((?<![A-Z0-9_?&-])(?=[A-Z_][A-Z0-9_]*\s*=)"
            rf"[A-Z0-9_]*{_SENSITIVE_NAME}"
            rf"[A-Z0-9_]*\s*=\s*){_VALUE}"
        ),
        rf"\1{REDACTED}",
    ),
    (
        re.compile(rf"(?i)(--{_SENSITIVE_OPTION}(?:\s+|=)){_VALUE}"),
        rf"\1{REDACTED}",
    ),
    (
        re.compile(
            r"(?i)(\b(?:authorization|proxy-authorization|x-api-key|api-key|"
            r"x-auth-token|cookie)\s*:\s*(?:(?:Bearer|Basic)\s+)?)"
            r"[^\s'\"]+"
        ),
        rf"\1{REDACTED}",
    ),
    (
        re.compile(r"(?i)(\b(?:Bearer|Basic)\s+)[A-Za-z0-9._~+/=-]+"),
        rf"\1{REDACTED}",
    ),
    (
        re.compile(r"(?i)((?:https?|ssh)://[^\s:/@]+:)[^\s/@]+@"),
        rf"\1{REDACTED}@",
    ),
    (
        re.compile(rf"(?i)([?&][A-Z0-9_]*{_SENSITIVE_NAME}[A-Z0-9_]*=)[^&\s'\"]+"),
        rf"\1{REDACTED}",
    ),
    (
        re.compile(r"(?i)((?:-u|--user)\s+['\"]?[^:\s'\"]+:)[^\s'\"]+"),
        rf"\1{REDACTED}",
    ),
    (re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b"), REDACTED),
)


def redact_command(command: str) -> str:
    """Return *command* with common inline credential forms removed."""

    redacted = command
    for pattern, replacement in _PATTERNS:
        redacted = pattern.sub(replacement, redacted)
    return redacted
