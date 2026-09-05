"""Measure database writes, CLI writes, and asynchronous process submission."""

from __future__ import annotations

import argparse
import os
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path


ROOT = Path(__file__).parents[1]
sys.path.insert(0, str(ROOT / "src"))

from why.db import ShellMemory  # noqa: E402


def _milliseconds(samples: list[float]) -> tuple[float, float]:
    ordered = sorted(samples)
    p95 = ordered[min(len(ordered) - 1, int(len(ordered) * 0.95))]
    return statistics.median(ordered) * 1000, p95 * 1000


def _print_result(name: str, samples: list[float]) -> None:
    median, p95 = _milliseconds(samples)
    print(f"{name:<24} median={median:8.2f} ms  p95={p95:8.2f} ms")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--direct-iterations", type=int, default=500)
    parser.add_argument("--process-iterations", type=int, default=25)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as directory:
        database_path = Path(directory) / "why.db"
        memory = ShellMemory(database_path)
        direct_samples = []
        for index in range(args.direct_iterations):
            started = time.perf_counter()
            now = time.time()
            memory.record_event("benchmark", f"true #{index}", "/tmp", "/tmp", now, now, 0)
            direct_samples.append(time.perf_counter() - started)

        environment = os.environ.copy()
        environment.update(
            {
                "PYTHONPATH": str(ROOT / "src"),
                "WHY_DB_PATH": str(database_path),
                "WHY_CONFIG_PATH": str(Path(directory) / "missing.toml"),
                "WHY_SESSION_ID": "benchmark-cli",
                "WHY_RETENTION_DAYS": "0",
                "WHY_MAX_EVENTS_PER_SESSION": "0",
            }
        )
        command = [
            sys.executable,
            "-m",
            "why",
            "internal",
            "record",
            "--command",
            "true",
            "--cwd-before",
            "/tmp",
            "--cwd-after",
            "/tmp",
            "--started-at",
            str(time.time()),
            "--exit-code",
            "0",
        ]
        cli_samples = []
        launch_samples = []
        for _ in range(args.process_iterations):
            started = time.perf_counter()
            subprocess.run(command, env=environment, check=True, capture_output=True)
            cli_samples.append(time.perf_counter() - started)

            started = time.perf_counter()
            process = subprocess.Popen(
                command,
                env=environment,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            launch_samples.append(time.perf_counter() - started)
            process.wait()

    _print_result("direct SQLite write", direct_samples)
    _print_result("CLI write end-to-end", cli_samples)
    _print_result("async process launch", launch_samples)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
