"""Unit tests for configuration management (Pydantic Settings)."""

import os
import unittest
from unittest.mock import patch

from pydantic import SecretStr
from app.core.config import Settings, get_settings


class TestConfiguration(unittest.TestCase):
    """Test suite for application settings."""

    def test_default_settings(self):
        """Verify default development configuration."""
        settings = Settings()
        self.assertEqual(settings.APP_NAME, "RelayPoint")
        self.assertEqual(settings.APP_ENV, "development")
        self.assertTrue(settings.APP_DEBUG)
        self.assertEqual(settings.APP_HOST, "127.0.0.1")
        self.assertEqual(settings.APP_PORT, 8000)
        self.assertEqual(settings.API_VERSION, "0.1.0")
        self.assertIn("http://localhost:5173", settings.CORS_ORIGINS)

    def test_secret_protection(self):
        """Verify secrets are wrapped in SecretStr and not exposed in string representations."""
        settings = Settings(
            SECRET_KEY=SecretStr("my-super-secret-key-12345"),
            GITHUB_TOKEN=SecretStr("ghp_fakeTokenValueForTestingOnly123456"),
            GEMINI_API_KEY=SecretStr("AIzaSyFakeGeminiApiKeyForTesting12345"),
        )

        repr_str = repr(settings)
        str_val = str(settings)

        # Secrets must NOT appear in raw string representations
        self.assertNotIn("my-super-secret-key-12345", repr_str)
        self.assertNotIn("ghp_fakeTokenValueForTestingOnly123456", repr_str)
        self.assertNotIn("AIzaSyFakeGeminiApiKeyForTesting12345", repr_str)

        self.assertNotIn("my-super-secret-key-12345", str_val)
        self.assertNotIn("ghp_fakeTokenValueForTestingOnly123456", str_val)

        # Safe summary must not leak raw secrets
        summary = settings.safe_summary()
        self.assertTrue(summary["github_token_configured"])
        self.assertTrue(summary["gemini_api_key_configured"])
        self.assertNotIn("ghp_fakeTokenValueForTestingOnly123456", str(summary))

    def test_cors_origin_parsing(self):
        """Verify comma-separated origins string parses into clean list."""
        settings = Settings(
            CORS_ORIGINS="http://localhost:3000, https://relaypoint.app , http://127.0.0.1:8080",
            _env_file=None,
        )
        self.assertEqual(
            settings.CORS_ORIGINS,
            ["http://localhost:3000", "https://relaypoint.app", "http://127.0.0.1:8080"],
        )

    def test_database_path_resolution(self):
        """Verify SQLite path and URL parsing."""
        settings_path = Settings(DATABASE_PATH="custom.db", DATABASE_URL=None, _env_file=None)
        self.assertTrue(str(settings_path.get_database_path()).endswith("custom.db"))

        settings_url = Settings(DATABASE_URL="sqlite:///./nested/test.db", _env_file=None)
        self.assertTrue(str(settings_url.get_database_path()).endswith("test.db"))

    def test_env_validation(self):
        """Verify invalid environment stages are rejected."""
        with self.assertRaises(ValueError):
            Settings(APP_ENV="unsupported_environment_mode")


if __name__ == "__main__":
    unittest.main()
