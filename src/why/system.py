"""Collection of deliberately small, non-secret system context."""

from __future__ import annotations

import os
import platform
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GitContext:
    branch: str | None
    commit: str | None
    dirty: bool | None


@dataclass(frozen=True)
class SystemContext:
    os_name: str
    shell: str
    cwd: str
    git: GitContext


def collect_git_context(cwd: str | Path) -> GitContext:
    """Collect branch, short commit and dirty state, if *cwd* is in Git."""

    directory = str(cwd)

    def git(*args: str) -> str | None:
        try:
            result = subprocess.run(
                ["git", *args],
                cwd=directory,
                check=True,
                capture_output=True,
                text=True,
                timeout=2,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        return result.stdout.strip()

    commit = git("rev-parse", "--short", "HEAD")
    if commit is None:
        return GitContext(branch=None, commit=None, dirty=None)

    branch = git("branch", "--show-current") or "(detached HEAD)"
    status = git("status", "--porcelain")
    return GitContext(branch=branch, commit=commit, dirty=status != "")


def collect_system_context(cwd: str | None = None) -> SystemContext:
    current_directory = cwd or os.getcwd()
    shell_path = os.environ.get("SHELL", "zsh")
    return SystemContext(
        os_name=f"{platform.system()} {platform.release()}",
        shell=os.path.basename(shell_path),
        cwd=current_directory,
        git=collect_git_context(current_directory),
    )
