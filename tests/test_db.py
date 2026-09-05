import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

from why.db import DatabaseVersionError, ShellMemory


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

    def test_atomic_record_event(self):
        event_id = self.memory.record_event(
            "session-a", "false", "/before", "/after", 1.0, 1.25, 1
        )

        event = self.memory.get_event("session-a", event_id)
        self.assertEqual(event.command_raw, "false")
        self.assertEqual(event.cwd_after, "/after")
        self.assertEqual(event.exit_code, 1)
        self.assertAlmostEqual(event.duration, 0.25)

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

    def test_database_is_private_and_commands_are_redacted(self):
        path = Path(self.temp_dir.name) / "private" / "why.db"
        memory = ShellMemory(path)
        memory.begin_event(
            "session-a",
            "API_TOKEN=top-secret curl --password hunter2 https://example.test",
            "/tmp",
            1.0,
        )

        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(path.parent.stat().st_mode), 0o700)
        command = memory.get_recent_events("session-a")[0].command_raw
        self.assertNotIn("top-secret", command)
        self.assertNotIn("hunter2", command)
        self.assertEqual(command.count("<redacted>"), 2)

    def test_existing_database_permissions_are_tightened(self):
        path = Path(self.temp_dir.name) / "existing.db"
        path.write_bytes(b"")
        path.chmod(0o644)

        ShellMemory(path).all_sessions()

        self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)

    def test_existing_schema_is_migrated_and_data_is_preserved(self):
        path = Path(self.temp_dir.name) / "legacy.db"
        with sqlite3.connect(path) as connection:
            connection.executescript(
                """
                CREATE TABLE sessions (id TEXT PRIMARY KEY, started_at REAL NOT NULL);
                CREATE TABLE shell_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    command_raw TEXT NOT NULL,
                    cwd_before TEXT NOT NULL,
                    cwd_after TEXT,
                    started_at REAL NOT NULL,
                    ended_at REAL,
                    exit_code INTEGER
                );
                INSERT INTO sessions VALUES ('legacy', 1.0);
                INSERT INTO shell_events
                    (session_id, command_raw, cwd_before, cwd_after,
                     started_at, ended_at, exit_code)
                    VALUES ('legacy', 'false', '/tmp', '/tmp', 1.0, 1.1, 1);
                """
            )

        events = ShellMemory(path).get_recent_events("legacy")
        with sqlite3.connect(path) as connection:
            version = connection.execute("PRAGMA user_version").fetchone()[0]

        self.assertEqual(version, 2)
        self.assertEqual(events[0].command_raw, "false")

    def test_newer_schema_version_is_rejected(self):
        path = Path(self.temp_dir.name) / "future.db"
        with sqlite3.connect(path) as connection:
            connection.execute("PRAGMA user_version = 999")

        with self.assertRaisesRegex(DatabaseVersionError, "newer than supported"):
            ShellMemory(path).all_sessions()

    def test_prune_applies_age_and_per_session_count_limits(self):
        day = 86400.0
        old = self.memory.record_event("session-a", "old", "/tmp", "/tmp", day, day, 0)
        for index in range(4):
            started = 10 * day + index
            self.memory.record_event(
                "session-a", f"recent-{index}", "/tmp", "/tmp", started, started, 0
            )

        deleted = self.memory.prune(
            retention_days=5,
            max_events_per_session=2,
            session_id="session-a",
            now=10 * day + 10,
        )

        self.assertEqual(deleted, 3)
        self.assertIsNone(self.memory.get_event("session-a", old))
        self.assertEqual(
            [event.command_raw for event in self.memory.get_recent_events("session-a")],
            ["recent-2", "recent-3"],
        )

    def test_session_prune_keeps_other_empty_sessions(self):
        self.memory.create_session("empty-session", 1.0)
        self.memory.record_event("active", "true", "/tmp", "/tmp", 2, 3, 0)

        self.memory.prune(30, 5000, session_id="active", now=3)

        self.assertIn("empty-session", [session.id for session in self.memory.all_sessions()])

    def test_get_events_until_excludes_later_events(self):
        first = self.memory.begin_event("session-a", "false", "/tmp", 1.0)
        second = self.memory.begin_event("session-a", "true", "/tmp", 2.0)
        self.memory.end_event(first, 1, "/tmp", 1.1)
        self.memory.end_event(second, 0, "/tmp", 2.1)

        events = self.memory.get_events_until("session-a", first)
        self.assertEqual([event.id for event in events], [first])


if __name__ == "__main__":
    unittest.main()
