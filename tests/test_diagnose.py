import tempfile
import unittest
from pathlib import Path

from why.db import ShellMemory
from why.diagnose import diagnose


class FakeLLM:
    def __init__(self):
        self.prompt = None

    def complete(self, prompt):
        self.prompt = prompt
        return "based on the recorded events"


class DiagnoseTests(unittest.TestCase):
    def test_diagnose_uses_latest_failure_context(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ShellMemory(Path(directory) / "why.db")
            event_id = memory.begin_event("s", "false", "/tmp", 1.0)
            memory.end_event(event_id, 1, "/tmp", 1.1)
            llm = FakeLLM()

            result = diagnose(memory, "s", llm)

        self.assertEqual(result, "based on the recorded events")
        self.assertIn("command: false", llm.prompt)
        self.assertIn("exit_code: 1", llm.prompt)

    def test_no_failure_does_not_call_llm_for_default_diagnosis(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ShellMemory(Path(directory) / "why.db")
            llm = FakeLLM()

            result = diagnose(memory, "s", llm)

        self.assertIn("No failed shell command", result)
        self.assertIsNone(llm.prompt)


if __name__ == "__main__":
    unittest.main()
