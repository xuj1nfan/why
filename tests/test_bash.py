import os
import stat
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class BashIntegrationTests(unittest.TestCase):
    def test_hook_uses_one_atomic_background_record(self):
        hook = (ROOT / "src" / "why" / "why.bash").read_text(encoding="utf-8")
        self.assertIn("internal record", hook)
        self.assertNotIn("internal begin", hook)
        self.assertNotIn("internal end", hook)

    def test_interactive_bash_records_events(self):
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
                    f"source {ROOT / 'src' / 'why' / 'why.bash'}",
                    "cd /tmp",
                    "false",
                    "true && false",
                    "why history",
                    "exit",
                ]
            )
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-i"],
                input=commands + "\n",
                text=True,
                capture_output=True,
                env=environment,
                timeout=10,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("cd /tmp", result.stdout)
        self.assertIn("false", result.stdout)
        self.assertIn("true && false", result.stdout)
        self.assertNotIn("internal begin", result.stdout)
        self.assertNotIn("internal record", result.stdout)
        self.assertNotRegex(result.stdout, r"\[[0-9]+\]\s+[0-9]+")

    def test_existing_debug_and_prompt_hooks_are_preserved(self):
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
                    "WHY_CONFIG_PATH": str(temp_path / "missing-config.toml"),
                }
            )
            commands = "\n".join(
                [
                    "WHY_DEBUG_HITS=0",
                    "trap '((WHY_DEBUG_HITS+=1))' DEBUG",
                    "WHY_PROMPT_HITS=0",
                    "PROMPT_COMMAND='((WHY_PROMPT_HITS+=1))'",
                    f"source {ROOT / 'src' / 'why' / 'why.bash'}",
                    "true",
                    "printf 'HOOK_COUNTS:%s:%s\\n' \"$WHY_DEBUG_HITS\" \"$WHY_PROMPT_HITS\"",
                    "exit",
                ]
            )
            result = subprocess.run(
                ["bash", "--noprofile", "--norc", "-i"],
                input=commands + "\n",
                text=True,
                capture_output=True,
                env=environment,
                timeout=10,
                check=False,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertRegex(result.stdout, r"HOOK_COUNTS:[1-9][0-9]*:[1-9][0-9]*")


if __name__ == "__main__":
    unittest.main()
