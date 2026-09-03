import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from why.config import get_config


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


if __name__ == "__main__":
    unittest.main()
