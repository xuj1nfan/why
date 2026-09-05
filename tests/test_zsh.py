import os
import shutil
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path

from why.db import ShellMemory


ROOT = Path(__file__).parents[1]


class ZshHookTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("zsh"), "zsh is not installed")
    def test_interactive_zsh_records_commands_and_statuses(self):
        with tempfile.TemporaryDirectory() as directory:
            temp_path = Path(directory)
            wrapper = temp_path / "why"
            wrapper.write_text(
                "#!/bin/sh\nexec python3 -m why \"$@\"\n",
                encoding="utf-8",
            )
            wrapper.chmod(wrapper.stat().st_mode | stat.S_IXUSR)
            environment = os.environ.copy()
            environment.update(
                {
                    "PATH": f"{temp_path}:{environment['PATH']}",
                    "PYTHONPATH": str(ROOT / "src"),
                    "WHY_DB_PATH": str(temp_path / "why.db"),
                    "WHY_SESSION_ID": "",
                    "WHY_CONFIG_PATH": str(temp_path / "missing-config.toml"),
                }
            )
            commands = "\n".join(
                [
                    f"source {ROOT / 'src' / 'why' / 'why.zsh'}",
                    "cd /tmp",
                    "false",
                    "true",
                    "exit",
                ]
            )
            result = subprocess.run(
                [shutil.which("zsh"), "-f", "-i"],
                input=commands + "\n",
                text=True,
                capture_output=True,
                env=environment,
                timeout=10,
                check=False,
            )
            memory = ShellMemory(temp_path / "why.db")
            sessions = list(memory.all_sessions())
            completed = [
                (event.command_raw, event.exit_code)
                for event in memory.get_recent_events(sessions[0].id)
                if event.exit_code is not None
            ]

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(completed, [("cd /tmp", 0), ("false", 1), ("true", 0)])
        self.assertNotIn("internal record", result.stdout)
        self.assertNotRegex(result.stdout, r"\[[0-9]+\]\s+[0-9]+")

    def test_packaged_hook_contains_lifecycle_safety_guards(self):
        hook = (ROOT / "src" / "why" / "why.zsh").read_text(encoding="utf-8")
        self.assertIn("add-zsh-hook preexec _why_preexec", hook)
        self.assertIn("add-zsh-hook precmd _why_precmd", hook)
        self.assertIn('WHY_SESSION_PID:-}" != "$$"', hook)
        self.assertIn('[[ "$command" == "why"', hook)
        self.assertIn('return "$exit_code"', hook)
        self.assertIn("internal session", hook)
        self.assertIn("internal record", hook)
        self.assertNotIn("internal begin", hook)
        self.assertNotIn("internal end", hook)

    def test_checkout_entrypoint_uses_packaged_hook(self):
        entrypoint = (ROOT / "shell" / "why.zsh").read_text(encoding="utf-8")
        self.assertIn("src/why/why.zsh", entrypoint)


if __name__ == "__main__":
    unittest.main()
