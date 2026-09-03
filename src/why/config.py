"""Configuration for local why data."""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    model: str | None = None
    timeout: float = 30.0


@dataclass(frozen=True)
class WhyConfig:
    database_path: Path
    llm: LLMConfig


def default_database_path() -> Path:
    """Resolve the database path without creating it."""

    explicit_path = os.environ.get("WHY_DB_PATH")
    if explicit_path:
        return Path(explicit_path).expanduser()

    data_home = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share")).expanduser()
    return data_home / "why" / "why.db"


def default_config_path() -> Path:
    explicit_path = os.environ.get("WHY_CONFIG_PATH")
    if explicit_path:
        return Path(explicit_path).expanduser()

    config_home = Path(os.environ.get("XDG_CONFIG_HOME", "~/.config")).expanduser()
    return config_home / "why" / "config.toml"


def _load_file_config(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open("rb") as config_file:
        return tomllib.load(config_file)


def get_config() -> WhyConfig:
    file_config = _load_file_config(default_config_path())
    file_llm = file_config.get("llm", {})
    llm = LLMConfig(
        base_url=os.environ.get("WHY_LLM_BASE_URL", file_llm.get("base_url", LLMConfig.base_url)),
        api_key_env=os.environ.get("WHY_LLM_API_KEY_ENV", file_llm.get("api_key_env", LLMConfig.api_key_env)),
        model=os.environ.get("WHY_LLM_MODEL", file_llm.get("model")),
        timeout=float(os.environ.get("WHY_LLM_TIMEOUT", file_llm.get("timeout", LLMConfig.timeout))),
    )
    return WhyConfig(database_path=default_database_path(), llm=llm)
