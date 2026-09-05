"""Configuration for local why data."""

from __future__ import annotations

import math
import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class LLMConfig:
    base_url: str = "https://api.openai.com/v1"
    api_key_env: str = "OPENAI_API_KEY"
    model: str | None = None
    timeout: float = 30.0


@dataclass(frozen=True)
class StorageConfig:
    retention_days: int = 30
    max_events_per_session: int = 5000


@dataclass(frozen=True)
class WhyConfig:
    database_path: Path
    llm: LLMConfig
    storage: StorageConfig = field(default_factory=StorageConfig)


class ConfigError(ValueError):
    """A configuration file or setting cannot be used safely."""


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
    try:
        with path.open("rb") as config_file:
            return tomllib.load(config_file)
    except tomllib.TOMLDecodeError as error:
        raise ConfigError(f"cannot parse {path}: {error}") from error
    except OSError as error:
        raise ConfigError(f"cannot read {path}: {error}") from error


def get_config() -> WhyConfig:
    file_config = _load_file_config(default_config_path())
    file_llm = file_config.get("llm", {})
    file_storage = file_config.get("storage", {})
    if not isinstance(file_llm, dict):
        raise ConfigError("the [llm] configuration must be a TOML table")
    if not isinstance(file_storage, dict):
        raise ConfigError("the [storage] configuration must be a TOML table")

    base_url = os.environ.get("WHY_LLM_BASE_URL", file_llm.get("base_url", LLMConfig.base_url))
    api_key_env = os.environ.get(
        "WHY_LLM_API_KEY_ENV", file_llm.get("api_key_env", LLMConfig.api_key_env)
    )
    model = os.environ.get("WHY_LLM_MODEL", file_llm.get("model"))
    timeout_value = os.environ.get("WHY_LLM_TIMEOUT", file_llm.get("timeout", LLMConfig.timeout))

    if not isinstance(base_url, str) or not base_url.strip():
        raise ConfigError("llm.base_url must be a non-empty string")
    if not isinstance(api_key_env, str) or not api_key_env.strip():
        raise ConfigError("llm.api_key_env must be a non-empty string")
    if model is not None and not isinstance(model, str):
        raise ConfigError("llm.model must be a string")
    try:
        timeout = float(timeout_value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ConfigError("llm.timeout must be a number") from error
    if not math.isfinite(timeout) or timeout <= 0:
        raise ConfigError("llm.timeout must be a finite number greater than zero")

    retention_days = _non_negative_int(
        "storage.retention_days",
        os.environ.get(
            "WHY_RETENTION_DAYS",
            file_storage.get("retention_days", StorageConfig.retention_days),
        ),
    )
    max_events = _non_negative_int(
        "storage.max_events_per_session",
        os.environ.get(
            "WHY_MAX_EVENTS_PER_SESSION",
            file_storage.get("max_events_per_session", StorageConfig.max_events_per_session),
        ),
    )

    llm = LLMConfig(
        base_url=base_url.strip(),
        api_key_env=api_key_env.strip(),
        model=model.strip() if isinstance(model, str) and model.strip() else None,
        timeout=timeout,
    )
    storage = StorageConfig(
        retention_days=retention_days,
        max_events_per_session=max_events,
    )
    return WhyConfig(database_path=default_database_path(), llm=llm, storage=storage)


def _non_negative_int(name: str, value: object) -> int:
    if isinstance(value, bool):
        raise ConfigError(f"{name} must be a non-negative integer")
    try:
        result = int(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ConfigError(f"{name} must be a non-negative integer") from error
    if result < 0 or isinstance(value, float) and not value.is_integer():
        raise ConfigError(f"{name} must be a non-negative integer")
    return result
