import tempfile
import unittest
from pathlib import Path

from why.db import ShellMemory


class ShellMemoryTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.memory = ShellMemory(Path(self.temp_dir.name) / "why.db")

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_event_lifecycle_and_recent_order(self):
        first = self.memory.begin_event("session-a", "cd /tmp", "/home/user", 1.0)
        second = self.memory.begin_event("session-a", "false", "/tmp", 2.0)
        self.memory.end_event(first, 0, "/tmp", 2.1)
        self.memory.end_event(second, 1, "/tmp", 2.2)

        events = self.memory.get_recent_events("session-a")
        self.assertEqual([event.id for event in events], [first, second])
        self.assertEqual(events[0].cwd_after, "/tmp")
        self.assertEqual(events[1].exit_code, 1)
        self.assertAlmostEqual(events[1].duration, 0.2)
        self.assertEqual(self.memory.get_latest_failed_event("session-a").id, second)

    def test_sessions_are_isolated(self):
        event_id = self.memory.begin_event("session-a", "false", "/tmp", 1.0)
        self.memory.end_event(event_id, 1, "/tmp", 1.1)

        self.assertEqual(self.memory.get_recent_events("session-b"), [])
        self.assertIsNone(self.memory.get_latest_failed_event("session-b"))

    def test_clear_session(self):
        event_id = self.memory.begin_event("session-a", "true", "/tmp", 1.0)
        self.memory.begin_event("session-b", "true", "/tmp", 2.0)
        self.memory.end_event(event_id, 0, "/tmp", 1.1)

        self.assertEqual(self.memory.clear("session-a"), 1)
        self.assertEqual(self.memory.get_recent_events("session-a"), [])
        self.assertEqual(len(self.memory.get_recent_events("session-b")), 1)

    def test_incomplete_event_is_readable(self):
        event_id = self.memory.begin_event("session-a", "sleep 10", "/tmp", 1.0)
        event = self.memory.get_recent_events("session-a")[0]
        self.assertEqual(event.id, event_id)
        self.assertIsNone(event.exit_code)
        self.assertIsNone(event.duration)

    def test_get_events_until_excludes_later_events(self):
        first = self.memory.begin_event("session-a", "false", "/tmp", 1.0)
        second = self.memory.begin_event("session-a", "true", "/tmp", 2.0)
        self.memory.end_event(first, 1, "/tmp", 1.1)
        self.memory.end_event(second, 0, "/tmp", 2.1)

        events = self.memory.get_events_until("session-a", first)
        self.assertEqual([event.id for event in events], [first])


if __name__ == "__main__":
    unittest.main()
