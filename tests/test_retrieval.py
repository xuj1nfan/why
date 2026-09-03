import tempfile
import unittest
from pathlib import Path

from why.db import ShellMemory
from why.retrieval import get_diagnosis_events


class RetrievalTests(unittest.TestCase):
    def test_latest_failure_is_context_boundary(self):
        with tempfile.TemporaryDirectory() as directory:
            memory = ShellMemory(Path(directory) / "why.db")
            first = memory.begin_event("s", "cd /tmp", "/home", 1.0)
            failure = memory.begin_event("s", "false", "/tmp", 2.0)
            later = memory.begin_event("s", "true", "/tmp", 3.0)
            memory.end_event(first, 0, "/tmp", 1.1)
            memory.end_event(failure, 1, "/tmp", 2.1)
            memory.end_event(later, 0, "/tmp", 3.1)

            failed, events = get_diagnosis_events(memory, "s", limit=15)
            self.assertEqual(failed.id, failure)
            self.assertEqual([event.id for event in events], [first, failure])


if __name__ == "__main__":
    unittest.main()
