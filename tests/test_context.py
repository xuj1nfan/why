import unittest

from why.context import build_context
from why.models import ShellEvent
from why.system import GitContext, SystemContext


class ContextTests(unittest.TestCase):
    def test_context_is_structured_and_does_not_include_environment(self):
        event = ShellEvent(1, "s", "false", "/tmp", "/tmp", 1.0, 1.2, 1)
        context = build_context(
            [event],
            SystemContext("Linux test", "zsh", "/tmp", GitContext("main", "abc123", False)),
        )
        self.assertIn("command: false", context)
        self.assertIn("exit_code: 1", context)
        self.assertIn("branch: main", context)
        self.assertIn("does not capture stdout/stderr", context)
        self.assertNotIn("OPENAI_API_KEY", context)


if __name__ == "__main__":
    unittest.main()
