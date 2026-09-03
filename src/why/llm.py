"""Minimal OpenAI-compatible chat-completions client."""

from __future__ import annotations

import json
import os
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import LLMConfig


class LLMError(RuntimeError):
    """An expected configuration, transport, or response error."""


class LLMClient:
    def __init__(self, config: LLMConfig, opener: Callable[..., Any] = urlopen):
        self.config = config
        self._opener = opener

    def complete(self, prompt: str) -> str:
        api_key = os.environ.get(self.config.api_key_env)
        if not api_key:
            raise LLMError(
                f"Missing API key. Set {self.config.api_key_env} or configure llm.api_key_env."
            )
        if not self.config.model:
            raise LLMError("No LLM model configured. Set WHY_LLM_MODEL or llm.model in config.toml.")

        endpoint = self.config.base_url.rstrip("/") + "/chat/completions"
        payload = {
            "model": self.config.model,
            "messages": [
                {"role": "system", "content": "You are a careful shell debugging assistant."},
                {"role": "user", "content": prompt},
            ],
        }
        request = Request(
            endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

        try:
            with self._opener(request, timeout=self.config.timeout) as response:
                body = response.read()
        except HTTPError as error:
            raise LLMError(f"LLM request failed with HTTP {error.code}.") from error
        except (URLError, TimeoutError, OSError) as error:
            raise LLMError(f"LLM request failed: {error.reason if hasattr(error, 'reason') else error}.") from error

        try:
            data = json.loads(body)
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as error:
            raise LLMError("LLM returned an invalid chat-completions response.") from error

        if not isinstance(content, str) or not content.strip():
            raise LLMError("LLM returned an empty diagnosis.")
        return content.strip()
