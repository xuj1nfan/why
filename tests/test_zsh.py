import unittest
from pathlib import Path


ROOT = Path(__file__).parents[1]


class ZshHookTests(unittest.TestCase):
    def test_packaged_hook_contains_lifecycle_safety_guards(self):
        hook = (ROOT / "src" / "why" / "why.zsh").read_text(encoding="utf-8")
        self.assertIn("add-zsh-hook preexec _why_preexec", hook)
        self.assertIn("add-zsh-hook precmd _why_precmd", hook)
        self.assertIn('WHY_SESSION_PID:-}" != "$$"', hook)
        self.assertIn('[[ "$command" == "why"', hook)
        self.assertIn('return "$exit_code"', hook)
        self.assertIn("internal session", hook)

    def test_checkout_entrypoint_uses_packaged_hook(self):
        entrypoint = (ROOT / "shell" / "why.zsh").read_text(encoding="utf-8")
        self.assertIn("src/why/why.zsh", entrypoint)


if __name__ == "__main__":
    unittest.main()
