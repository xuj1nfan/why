import unittest

from why.redaction import redact_command


class RedactionTests(unittest.TestCase):
    def test_redacts_common_credential_forms(self):
        cases = {
            "TOKEN=secret command": "TOKEN=<redacted> command",
            "AWS_SECRET_ACCESS_KEY='secret value' command": (
                "AWS_SECRET_ACCESS_KEY=<redacted> command"
            ),
            "curl --api-key=secret https://example.test": (
                "curl --api-key=<redacted> https://example.test"
            ),
            "curl -H 'Authorization: Bearer abc.def-123'": (
                "curl -H 'Authorization: Bearer <redacted>'"
            ),
            "curl -H 'X-Api-Key: abc.def-123'": (
                "curl -H 'X-Api-Key: <redacted>'"
            ),
            "tool --github-token secret": "tool --github-token <redacted>",
            "curl https://user:password@example.test": (
                "curl https://user:<redacted>@example.test"
            ),
            "curl 'https://example.test?a=1&token=secret'": (
                "curl 'https://example.test?a=1&token=<redacted>'"
            ),
            "curl 'https://example.test?id_token=secret'": (
                "curl 'https://example.test?id_token=<redacted>'"
            ),
            "curl -u user:password https://example.test": (
                "curl -u user:<redacted> https://example.test"
            ),
        }
        for command, expected in cases.items():
            with self.subTest(command=command):
                self.assertEqual(redact_command(command), expected)

    def test_leaves_normal_command_unchanged(self):
        commands = [
            "git log --oneline --max-count=5",
            "tool --tokenizer wordpiece",
            "git commit --author 'Example <example@test>'",
        ]
        for command in commands:
            with self.subTest(command=command):
                self.assertEqual(redact_command(command), command)


if __name__ == "__main__":
    unittest.main()
