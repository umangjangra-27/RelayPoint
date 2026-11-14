"""Unit tests for deterministic secret sanitization using synthetic credentials."""

import unittest
from app.utils.sanitizer import REDACTION_TOKEN, sanitize_text, sanitize_with_report


class TestSecretSanitizer(unittest.TestCase):
    """Test suite for credential sanitization."""

    def test_github_tokens(self):
        """Verify GitHub Personal Access Token redaction."""
        # Synthetic fake tokens
        fake_classic = "ghp_1234567890abcdefghijklmnopqrstuvwxyzAB"
        fake_fine_grained = "github_pat_11AEXAMPLE0000000000000_fakePayloadHereForTestingOnlyStrictlySynthetic1234567890abcdef"

        diff_content = f"git clone https://{fake_classic}@github.com/org/repo.git\nexport PAT={fake_fine_grained}"
        sanitized = sanitize_text(diff_content)

        self.assertNotIn(fake_classic, sanitized)
        self.assertNotIn(fake_fine_grained, sanitized)
        self.assertIn(REDACTION_TOKEN, sanitized)

    def test_api_keys(self):
        """Verify OpenAI, Google, AWS, and Slack key redactions."""
        fake_google = "AIzaSyFakeKeyGooglePayloadForTesting1"
        fake_openai = "sk-fakeOpenAiKeyWithEnoughLengthForMatch123456"
        fake_aws = "AKIAIOSFODNN7EXAMPLE"
        fake_slack = "fake-slack-token-for-testing"

        text = (
            f"GEMINI_API_KEY = '{fake_google}'\n"
            f"OPENAI_KEY = '{fake_openai}'\n"
            f"AWS_ACCESS_KEY_ID = '{fake_aws}'\n"
            f"SLACK_BOT_TOKEN = '{fake_slack}'\n"
        )
        report = sanitize_with_report(text)

        self.assertNotIn(fake_google, report.sanitized_text)
        self.assertNotIn(fake_openai, report.sanitized_text)
        self.assertNotIn(fake_aws, report.sanitized_text)
        self.assertNotIn(fake_slack, report.sanitized_text)
        self.assertGreaterEqual(report.redactions_count, 4)

    def test_bearer_token(self):
        """Verify Bearer token authorization header redaction."""
        fake_bearer = "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.syntheticFakeTokenPayload.signature"
        text = f"curl -H 'Authorization: {fake_bearer}' https://api.example.com"

        sanitized = sanitize_text(text)
        self.assertNotIn("syntheticFakeTokenPayload", sanitized)
        self.assertIn(f"Bearer {REDACTION_TOKEN}", sanitized)

    def test_database_connection_uri(self):
        """Verify database credentials are redacted while preserving host and protocol."""
        fake_pg_uri = "postgresql://dbuser:SuperSecretPass123@db.internal.net:5432/production_db"
        fake_redis_uri = "redis://default:AnotherSecretRedisPass@cache.internal:6379/0"

        text = f"DATABASE_URL={fake_pg_uri}\nREDIS_URL={fake_redis_uri}"
        sanitized = sanitize_text(text)

        self.assertNotIn("SuperSecretPass123", sanitized)
        self.assertNotIn("AnotherSecretRedisPass", sanitized)
        self.assertIn(f"postgresql://dbuser:{REDACTION_TOKEN}@db.internal.net:5432/production_db", sanitized)
        self.assertIn(f"redis://default:{REDACTION_TOKEN}@cache.internal:6379/0", sanitized)

    def test_password_assignments(self):
        """Verify config password assignments are redacted while preserving variable names."""
        text = 'password = "SyntheticPassword_999!"\nclient_secret: "SyntheticSecret_XYZ"'
        sanitized = sanitize_text(text)

        self.assertNotIn("SyntheticPassword_999!", sanitized)
        self.assertNotIn("SyntheticSecret_XYZ", sanitized)
        self.assertIn(f'password = "{REDACTION_TOKEN}"', sanitized)
        self.assertIn(f'client_secret: "{REDACTION_TOKEN}"', sanitized)

    def test_private_key_pem(self):
        """Verify multi-line private keys are completely redacted."""
        fake_pem = (
            "-----BEGIN RSA PRIVATE KEY-----\n"
            "MIIEowIBAAKCAQEA0syntheticPayloadForTestingOnlyNotARealKey123456\n"
            "fakeLine2OfKeyDataABCDEFGHJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuv\n"
            "-----END RSA PRIVATE KEY-----"
        )
        text = f"Private key config:\n{fake_pem}\nKey loaded."
        sanitized = sanitize_text(text)

        self.assertNotIn("syntheticPayloadForTestingOnlyNotARealKey123456", sanitized)
        self.assertIn(REDACTION_TOKEN, sanitized)
        self.assertIn("Key loaded.", sanitized)

    def test_email_sanitization(self):
        """Verify developer emails can be redacted."""
        text = "Contact lead developer at john.doe@relaypoint.internal for access."
        sanitized = sanitize_text(text, redact_emails=True)

        self.assertNotIn("john.doe@relaypoint.internal", sanitized)
        self.assertIn(f"Contact lead developer at {REDACTION_TOKEN} for access.", sanitized)

    def test_context_preservation(self):
        """Verify non-sensitive code logic and syntax are untouched."""
        code = "def calculate_velocity(commits: list[str]) -> int:\n    return len(commits)"
        sanitized = sanitize_text(code)
        self.assertEqual(sanitized, code)


if __name__ == "__main__":
    unittest.main()
