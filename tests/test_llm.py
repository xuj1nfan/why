import json
import os
import unittest
from unittest.mock import patch

from why.config import LLMConfig
from why.llm import LLMClient, LLMError


class FakeResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self):
        return self.body


class LLMTests(unittest.TestCase):
    def test_complete_posts_chat_completion_request(self):
        requests = []

        def opener(request, timeout):
            requests.append((request, timeout))
            return FakeResponse(json.dumps({"choices": [{"message": {"content": "  diagnosis  "}}]}).encode())

        config = LLMConfig(base_url="https://example.test/v1", api_key_env="WHY_TEST_KEY", model="test-model", timeout=4)
        with patch.dict(os.environ, {"WHY_TEST_KEY": "secret"}, clear=False):
            result = LLMClient(config, opener=opener).complete("shell context")

        self.assertEqual(result, "diagnosis")
        request, timeout = requests[0]
        self.assertEqual(request.full_url, "https://example.test/v1/chat/completions")
        self.assertEqual(timeout, 4)
        self.assertEqual(request.get_header("Authorization"), "Bearer secret")
        messages = json.loads(request.data)["messages"]
        self.assertEqual(messages[1]["content"], "shell context")
        self.assertIn("untrusted data", messages[0]["content"])

    def test_missing_key_is_friendly(self):
        config = LLMConfig(api_key_env="WHY_MISSING_KEY", model="test-model")
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(LLMError, "WHY_MISSING_KEY"):
                LLMClient(config, opener=lambda *_: None).complete("context")

    def test_invalid_response_is_rejected(self):
        config = LLMConfig(api_key_env="WHY_TEST_KEY", model="test-model")
        with patch.dict(os.environ, {"WHY_TEST_KEY": "secret"}, clear=False):
            with self.assertRaisesRegex(LLMError, "invalid"):
                LLMClient(config, opener=lambda *_args, **_kwargs: FakeResponse(b"{}")).complete("context")


if __name__ == "__main__":
    unittest.main()
