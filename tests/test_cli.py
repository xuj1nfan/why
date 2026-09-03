import os
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from unittest.mock import patch

from why.cli import main


class CliTests(unittest.TestCase):
    def test_internal_begin_and_end_are_usable(self):
        with tempfile.TemporaryDirectory() as directory:
            old_db = os.environ.get("WHY_DB_PATH")
            old_session = os.environ.get("WHY_SESSION_ID")
            try:
                os.environ["WHY_DB_PATH"] = f"{directory}/why.db"
                os.environ["WHY_SESSION_ID"] = "cli-session"
                output = StringIO()
                with redirect_stdout(output):
                    self.assertEqual(main(["internal", "begin", "--command", "false", "--cwd", "/tmp"]), 0)
                event_id = output.getvalue().strip()
                self.assertTrue(event_id.isdigit())
                self.assertEqual(
                    main(["internal", "end", "--event-id", event_id, "--exit-code", "1", "--cwd", "/tmp"]),
                    0,
                )
            finally:
                if old_db is None:
                    os.environ.pop("WHY_DB_PATH", None)
                else:
                    os.environ["WHY_DB_PATH"] = old_db
                if old_session is None:
                    os.environ.pop("WHY_SESSION_ID", None)
                else:
                    os.environ["WHY_SESSION_ID"] = old_session

    def test_inspect_uses_recorded_events(self):
        with tempfile.TemporaryDirectory() as directory:
            old_db = os.environ.get("WHY_DB_PATH")
            old_session = os.environ.get("WHY_SESSION_ID")
            try:
                os.environ["WHY_DB_PATH"] = f"{directory}/why.db"
                os.environ["WHY_SESSION_ID"] = "inspect-session"
                event_output = StringIO()
                with redirect_stdout(event_output):
                    main(["internal", "begin", "--command", "false", "--cwd", "/tmp"])
                event_id = event_output.getvalue().strip()
                main(["internal", "end", "--event-id", event_id, "--exit-code", "1", "--cwd", "/tmp"])

                preview = StringIO()
                with redirect_stdout(preview):
                    self.assertEqual(main(["inspect"]), 0)
                self.assertIn("command: false", preview.getvalue())
                self.assertIn("exit_code: 1", preview.getvalue())
            finally:
                if old_db is None:
                    os.environ.pop("WHY_DB_PATH", None)
                else:
                    os.environ["WHY_DB_PATH"] = old_db
                if old_session is None:
                    os.environ.pop("WHY_SESSION_ID", None)
                else:
                    os.environ["WHY_SESSION_ID"] = old_session

    def test_default_diagnosis_reports_missing_api_key(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                os.environ,
                {
                    "WHY_DB_PATH": f"{directory}/why.db",
                    "WHY_CONFIG_PATH": f"{directory}/config.toml",
                    "WHY_SESSION_ID": "diagnose-session",
                    "WHY_LLM_API_KEY_ENV": "WHY_TEST_MISSING_KEY",
                    "WHY_TEST_MISSING_KEY": "",
                },
                clear=False,
            ):
                event_output = StringIO()
                with redirect_stdout(event_output):
                    main(["internal", "begin", "--command", "false", "--cwd", "/tmp"])
                main(
                    [
                        "internal",
                        "end",
                        "--event-id",
                        event_output.getvalue().strip(),
                        "--exit-code",
                        "1",
                        "--cwd",
                        "/tmp",
                    ]
                )
                error_output = StringIO()
                with patch("sys.stderr", new=error_output):
                    result = main([])

        self.assertEqual(result, 1)
        self.assertIn("WHY_TEST_MISSING_KEY", error_output.getvalue())

    def test_init_zsh_points_to_packaged_hook(self):
        output = StringIO()
        with redirect_stdout(output):
            result = main(["init", "zsh"])

        self.assertEqual(result, 0)
        hook_path = output.getvalue().splitlines()[1].removeprefix("source ").strip("'")
        self.assertTrue(hook_path.endswith("why.zsh"))
        self.assertTrue(os.path.isfile(hook_path))


if __name__ == "__main__":
    unittest.main()
