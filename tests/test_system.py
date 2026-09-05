import subprocess
import unittest
from unittest.mock import patch

from why.system import collect_git_context


class SystemContextTests(unittest.TestCase):
    def test_failed_status_collection_is_unknown_not_dirty(self):
        responses = [
            subprocess.CompletedProcess([], 0, stdout="abc123\n", stderr=""),
            subprocess.CompletedProcess([], 0, stdout="main\n", stderr=""),
            subprocess.TimeoutExpired(["git", "status"], 2),
        ]
        with patch("why.system.subprocess.run", side_effect=responses):
            context = collect_git_context("/tmp")

        self.assertEqual(context.branch, "main")
        self.assertEqual(context.commit, "abc123")
        self.assertIsNone(context.dirty)


if __name__ == "__main__":
    unittest.main()
