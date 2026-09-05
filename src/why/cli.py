"""Shell-native debugging assistant with local command memory."""

from __future__ import annotations

import argparse
import os
import shlex
import sys
import time
from datetime import datetime
from importlib.resources import files
from pathlib import Path

from . import __version__
from .config import ConfigError, get_config
from .context import MAX_ERROR_OUTPUT_CHARS
from .db import ShellMemory
from .diagnose import DiagnosisError, diagnose, prepare_diagnosis_context
from .llm import LLMClient, LLMError
from .recorder import begin_event, end_event, record_event


def _memory() -> ShellMemory:
    return ShellMemory(get_config().database_path)


def _session_id() -> str:
    return os.environ.get("WHY_SESSION_ID", "default")


def _format_time(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")


def _handle_history(args: argparse.Namespace) -> int:
    events = _memory().get_recent_events(_session_id(), limit=args.limit)
    if not events:
        print("No shell events recorded for this session.")
        return 0

    for event in events:
        status = "?" if event.exit_code is None else str(event.exit_code)
        cwd = event.cwd_after or event.cwd_before
        duration = ""
        if event.duration is not None:
            duration = f"  {event.duration:.2f}s"
        print(f"#{event.id:<5} {_format_time(event.started_at)}  {status:>3}  {cwd}{duration}")
        print(f"       {event.command_raw}")
    return 0


def _handle_begin(args: argparse.Namespace) -> int:
    event_id = begin_event(_memory(), _session_id(), args.command, args.cwd)
    print(event_id)
    return 0


def _handle_end(args: argparse.Namespace) -> int:
    end_event(_memory(), args.event_id, args.exit_code, args.cwd)
    return 0


def _handle_record(args: argparse.Namespace) -> int:
    config = get_config()
    memory = ShellMemory(config.database_path)
    record_event(
        memory,
        _session_id(),
        args.command,
        args.cwd_before,
        args.cwd_after,
        args.started_at,
        args.exit_code,
        retention_days=config.storage.retention_days,
        max_events_per_session=config.storage.max_events_per_session,
    )
    return 0


def _handle_session(args: argparse.Namespace) -> int:
    _memory().create_session(args.session_id, time.time())
    return 0


def _handle_clear(args: argparse.Namespace) -> int:
    count = _memory().clear(session_id=_session_id() if args.session else None)
    print(f"Cleared {count} event(s).")
    return 0


def _read_error_output(source: str | None) -> str | None:
    if source is None:
        return None
    if source == "-":
        chunks: list[str] = []
        length = 0
        while chunk := sys.stdin.read(8192):
            chunks.append(chunk)
            length += len(chunk)
            while length > MAX_ERROR_OUTPUT_CHARS * 2 and len(chunks) > 1:
                length -= len(chunks.pop(0))
        text = "".join(chunks)
        if len(text) > MAX_ERROR_OUTPUT_CHARS:
            return "... <beginning of error output omitted>\n" + text[-MAX_ERROR_OUTPUT_CHARS:]
        return text

    path = Path(source).expanduser()
    try:
        with path.open("rb") as output_file:
            output_file.seek(0, 2)
            size = output_file.tell()
            read_size = min(size, MAX_ERROR_OUTPUT_CHARS * 4)
            output_file.seek(-read_size, 2)
            data = output_file.read()
    except OSError as error:
        raise DiagnosisError(f"cannot read error output {path}: {error}") from error
    prefix = "... <beginning of error output omitted>\n" if size > read_size else ""
    return prefix + data.decode("utf-8", errors="replace")


def _handle_inspect(args: argparse.Namespace) -> int:
    _, prompt = prepare_diagnosis_context(
        _memory(),
        _session_id(),
        question=args.question,
        limit=args.limit,
        event_id=args.event,
        error_output=_read_error_output(args.output),
    )
    print("Context preview")
    print("───────────────")
    print(prompt)
    return 0


def _handle_prune(args: argparse.Namespace) -> int:
    config = get_config()
    days = config.storage.retention_days if args.days is None else args.days
    max_events = (
        config.storage.max_events_per_session if args.max_events is None else args.max_events
    )
    count = ShellMemory(config.database_path).prune(
        days,
        max_events,
        session_id=_session_id() if args.session else None,
    )
    print(f"Pruned {count} event(s).")
    return 0


def _handle_init_zsh(_: argparse.Namespace) -> int:
    print("# Add this to ~/.zshrc or evaluate it in the current shell.")
    print(f"source {shlex.quote(_zsh_hook_path())}")
    return 0


def _handle_init_bash(_: argparse.Namespace) -> int:
    print("# Add this to ~/.bashrc or evaluate it in the current shell.")
    print(f"source {shlex.quote(_bash_hook_path())}")
    return 0


def _zsh_hook_path() -> str:
    return str(files("why").joinpath("why.zsh"))


def _bash_hook_path() -> str:
    return str(files("why").joinpath("why.bash"))


def _handle_print_zsh_hook(_: argparse.Namespace) -> int:
    print(_zsh_hook_path())
    return 0


def _handle_print_bash_hook(_: argparse.Namespace) -> int:
    print(_bash_hook_path())
    return 0


def _handle_default(args: argparse.Namespace) -> int:
    config = get_config()
    try:
        result = diagnose(
            memory=ShellMemory(config.database_path),
            session_id=_session_id(),
            llm=LLMClient(config.llm),
            question=args.question,
            limit=getattr(args, "limit", 15),
            event_id=getattr(args, "event", None),
            error_output=_read_error_output(getattr(args, "output", None)),
        )
    except LLMError as error:
        print(f"why: {error}", file=sys.stderr)
        return 1
    print(result)
    return 0


def _add_diagnosis_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--limit", type=int, default=15, help="maximum context events")
    parser.add_argument("--event", type=int, help="diagnose a specific event ID")
    parser.add_argument(
        "--output",
        metavar="FILE",
        help="include error output from FILE, or - for stdin",
    )
    parser.add_argument("question", nargs="?", default=None, help="optional diagnosis question")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="why", description=__doc__)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument("--print-zsh-hook", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--print-bash-hook", action="store_true", help=argparse.SUPPRESS)
    subparsers = parser.add_subparsers(dest="subcommand")

    history = subparsers.add_parser("history", help="show shell memory for this session")
    history.add_argument("--limit", type=int, default=15)
    history.set_defaults(handler=_handle_history)

    clear = subparsers.add_parser("clear", help="delete recorded shell memory")
    clear.add_argument("--session", action="store_true", help="clear only this session")
    clear.set_defaults(handler=_handle_clear)

    prune = subparsers.add_parser("prune", help="apply shell-memory retention policy")
    prune.add_argument("--days", type=int, help="delete events older than this many days")
    prune.add_argument("--max-events", type=int, help="maximum events retained per session")
    prune.add_argument("--session", action="store_true", help="prune only this session")
    prune.set_defaults(handler=_handle_prune)

    inspect = subparsers.add_parser("inspect", help="preview the context for diagnosis")
    _add_diagnosis_arguments(inspect)
    inspect.set_defaults(handler=_handle_inspect)

    diagnose_parser = subparsers.add_parser("diagnose", help="diagnose a selected shell event")
    _add_diagnosis_arguments(diagnose_parser)
    diagnose_parser.set_defaults(handler=_handle_default)

    init = subparsers.add_parser("init", help="print shell integration setup")
    init_subparsers = init.add_subparsers(dest="shell", required=True)
    zsh = init_subparsers.add_parser("zsh", help="print zsh setup")
    zsh.set_defaults(handler=_handle_init_zsh)
    bash = init_subparsers.add_parser("bash", help="print bash setup")
    bash.set_defaults(handler=_handle_init_bash)

    internal = subparsers.add_parser("internal", help=argparse.SUPPRESS)
    internal_subparsers = internal.add_subparsers(dest="internal_command", required=True)
    begin = internal_subparsers.add_parser("begin", help=argparse.SUPPRESS)
    begin.add_argument("--command", required=True)
    begin.add_argument("--cwd", required=True)
    begin.set_defaults(handler=_handle_begin)
    end = internal_subparsers.add_parser("end", help=argparse.SUPPRESS)
    end.add_argument("--event-id", type=int, required=True)
    end.add_argument("--exit-code", type=int, required=True)
    end.add_argument("--cwd", required=True)
    end.set_defaults(handler=_handle_end)
    record = internal_subparsers.add_parser("record", help=argparse.SUPPRESS)
    record.add_argument("--command", required=True)
    record.add_argument("--cwd-before", required=True)
    record.add_argument("--cwd-after", required=True)
    record.add_argument("--started-at", type=float, required=True)
    record.add_argument("--exit-code", type=int, required=True)
    record.set_defaults(handler=_handle_record)
    session = internal_subparsers.add_parser("session", help=argparse.SUPPRESS)
    session.add_argument("--session-id", required=True)
    session.set_defaults(handler=_handle_session)

    parser.set_defaults(handler=_handle_default, question=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {"history", "clear", "prune", "inspect", "diagnose", "init", "internal"}
    try:
        if argv and not argv[0].startswith("-") and argv[0] not in commands:
            args = argparse.Namespace(question=" ".join(argv), handler=_handle_default)
            return args.handler(args)

        parser = build_parser()
        args = parser.parse_args(argv)
        if args.print_zsh_hook:
            return _handle_print_zsh_hook(args)
        if args.print_bash_hook:
            return _handle_print_bash_hook(args)
        return args.handler(args)
    except (ConfigError, DiagnosisError, ValueError) as error:
        prefix = "invalid configuration" if isinstance(error, ConfigError) else "error"
        print(f"why: {prefix}: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
