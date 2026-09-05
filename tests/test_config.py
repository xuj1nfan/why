import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from why.config import ConfigError, get_config


class ConfigTests(unittest.TestCase):
    def test_toml_config_and_environment_override(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text(
                "[llm]\nbase_url = 'https://config.test/v1'\nmodel = 'config-model'\ntimeout = 12\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "WHY_CONFIG_PATH": str(config_path),
                    "WHY_DB_PATH": str(Path(directory) / "memory.db"),
                    "WHY_LLM_MODEL": "env-model",
                },
                clear=False,
            ):
                config = get_config()

        self.assertEqual(config.database_path, Path(directory) / "memory.db")
        self.assertEqual(config.llm.base_url, "https://config.test/v1")
        self.assertEqual(config.llm.model, "env-model")
        self.assertEqual(config.llm.timeout, 12.0)
        self.assertEqual(config.storage.retention_days, 30)
        self.assertEqual(config.storage.max_events_per_session, 5000)

    def test_storage_config_and_environment_override(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text(
                "[storage]\nretention_days = 14\nmax_events_per_session = 1000\n",
                encoding="utf-8",
            )
            with patch.dict(
                os.environ,
                {
                    "WHY_CONFIG_PATH": str(config_path),
                    "WHY_MAX_EVENTS_PER_SESSION": "250",
                },
                clear=False,
            ):
                config = get_config()

        self.assertEqual(config.storage.retention_days, 14)
        self.assertEqual(config.storage.max_events_per_session, 250)

    def test_invalid_timeout_has_a_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text('[llm]\ntimeout = "soon"\n', encoding="utf-8")
            with patch.dict(os.environ, {"WHY_CONFIG_PATH": str(config_path)}, clear=False):
                with self.assertRaisesRegex(ConfigError, "timeout must be a number"):
                    get_config()

    def test_llm_section_must_be_a_table(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text('llm = "invalid"\n', encoding="utf-8")
            with patch.dict(os.environ, {"WHY_CONFIG_PATH": str(config_path)}, clear=False):
                with self.assertRaisesRegex(ConfigError, "must be a TOML table"):
                    get_config()

    def test_malformed_toml_has_a_configuration_error(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text("[llm\n", encoding="utf-8")
            with patch.dict(os.environ, {"WHY_CONFIG_PATH": str(config_path)}, clear=False):
                with self.assertRaisesRegex(ConfigError, "cannot parse"):
                    get_config()

    def test_infinite_retention_value_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            config_path = Path(directory) / "config.toml"
            config_path.write_text("[storage]\nretention_days = inf\n", encoding="utf-8")
            with patch.dict(os.environ, {"WHY_CONFIG_PATH": str(config_path)}, clear=False):
                with self.assertRaisesRegex(ConfigError, "non-negative integer"):
                    get_config()


if __name__ == "__main__":
    unittest.main()
