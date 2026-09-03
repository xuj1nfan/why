"""Command-line interface for the first why implementation pass."""

from __future__ import annotations

import argparse
import os
import shlex
import sys
import time
from datetime import datetime
from importlib.resources import files

from . import __version__
from .config import get_config
from .context import build_context
from .db import ShellMemory
from .diagnose import diagnose
from .llm import LLMClient, LLMError
from .recorder import begin_event, end_event
from .retrieval import get_diagnosis_events
from .system import collect_system_context


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


def _handle_session(args: argparse.Namespace) -> int:
    _memory().create_session(args.session_id, time.time())
    return 0


def _handle_clear(args: argparse.Namespace) -> int:
    count = _memory().clear(session_id=_session_id() if args.session else None)
    print(f"Cleared {count} event(s).")
    return 0


def _handle_inspect(args: argparse.Namespace) -> int:
    memory = _memory()
    _, events = get_diagnosis_events(memory, _session_id(), limit=args.limit)
    print("Context preview")
    print("───────────────")
    print(build_context(events, collect_system_context(), question=args.question))
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
        )
    except LLMError as error:
        print(f"why: {error}", file=sys.stderr)
        return 1
    print(result)
    return 0


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

    inspect = subparsers.add_parser("inspect", help="preview the context for diagnosis")
    inspect.add_argument("--limit", type=int, default=15)
    inspect.add_argument("question", nargs="?", default=None, help=argparse.SUPPRESS)
    inspect.set_defaults(handler=_handle_inspect)

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
    session = internal_subparsers.add_parser("session", help=argparse.SUPPRESS)
    session.add_argument("--session-id", required=True)
    session.set_defaults(handler=_handle_session)

    parser.set_defaults(handler=_handle_default, question=None)
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    commands = {"history", "clear", "inspect", "init", "internal"}
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


if __name__ == "__main__":
    raise SystemExit(main())
