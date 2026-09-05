import tempfile
import unittest
from pathlib import Path

from why.db import ShellMemory
from why.diagnose import DiagnosisError, diagnose


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
        self.assertIn('command: "false"', llm.prompt)
        self.assertIn("exit_code: 1", llm.prompt)

    def test_no_failure_does_not_call_llm_for_default_diagnosis(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ShellMemory(Path(directory) / "why.db")
            llm = FakeLLM()

            result = diagnose(memory, "s", llm)

        self.assertIn("No failed shell command", result)
        self.assertIsNone(llm.prompt)

    def test_explicit_question_uses_latest_events_after_a_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ShellMemory(Path(directory) / "why.db")
            failed = memory.begin_event("s", "old-failure", "/tmp", 1.0)
            memory.end_event(failed, 1, "/tmp", 1.1)
            latest = memory.begin_event("s", "latest-success", "/tmp", 2.0)
            memory.end_event(latest, 0, "/tmp", 2.1)
            llm = FakeLLM()

            diagnose(memory, "s", llm, question="Explain my latest command")

        self.assertIn("latest-success", llm.prompt)
        self.assertIn("Explain my latest command", llm.prompt)

    def test_specific_event_and_error_output_are_used(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ShellMemory(Path(directory) / "why.db")
            selected = memory.record_event("s", "compile", "/tmp", "/tmp", 1, 2, 2)
            memory.record_event("s", "later", "/tmp", "/tmp", 3, 4, 0)
            llm = FakeLLM()

            diagnose(
                memory,
                "s",
                llm,
                event_id=selected,
                error_output="TOKEN=secret\ncompiler: missing header",
            )

        self.assertIn("compile", llm.prompt)
        self.assertNotIn('command: "later"', llm.prompt)
        self.assertIn("compiler: missing header", llm.prompt)
        self.assertNotIn("TOKEN=secret", llm.prompt)
        self.assertIn(f"selected event #{selected}", llm.prompt)

    def test_unknown_selected_event_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ShellMemory(Path(directory) / "why.db")
            with self.assertRaisesRegex(DiagnosisError, "not found"):
                diagnose(memory, "s", FakeLLM(), event_id=999)

    def test_error_output_can_be_diagnosed_without_recorded_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            llm = FakeLLM()
            result = diagnose(
                ShellMemory(Path(directory) / "why.db"),
                "s",
                llm,
                error_output="compiler failed",
            )

        self.assertEqual(result, "based on the recorded events")
        self.assertIn("compiler failed", llm.prompt)

    def test_context_limit_must_include_at_least_one_event(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ShellMemory(Path(directory) / "why.db")
            with self.assertRaisesRegex(DiagnosisError, "at least 1"):
                diagnose(memory, "s", FakeLLM(), question="help", limit=0)


if __name__ == "__main__":
    unittest.main()
