"""Unit tests for lightweight Gemini API client integration."""

from io import BytesIO
import json
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from app.integrations.gemini import (
    GeminiAuthError,
    GeminiClient,
    GeminiError,
    GeminiModelNotFoundError,
    GeminiQuotaError,
    GeminiResponseError,
)


class TestGeminiClient(unittest.TestCase):
    """Test suite for Gemini REST client."""

    def test_missing_api_key_raises_auth_error(self):
        """Verify calling client without an API key immediately raises GeminiAuthError."""
        client = GeminiClient(api_key="")
        with self.assertRaises(GeminiAuthError):
            client.generate_structured_json(prompt="Test prompt")

    @patch("urllib.request.urlopen")
    def test_successful_structured_json_response(self, mock_urlopen):
        """Verify valid candidate payload extraction and JSON parsing."""
        mock_payload = {
            "candidates": [
                {
                    "content": {
                        "parts": [
                            {
                                "text": json.dumps({
                                    "project_summary": "Test project summary",
                                    "architectural_decisions": [],
                                })
                            }
                        ]
                    },
                    "finishReason": "STOP",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = GeminiClient(api_key="synthetic_fake_key", model="gemini-2.5-flash")
        result = client.generate_structured_json(prompt="Analyze repo")

        self.assertIn("project_summary", result)
        self.assertEqual(result["project_summary"], "Test project summary")

        # Verify API key is passed in header and NOT in URL query string
        sent_req = mock_urlopen.call_args[0][0]
        self.assertNotIn("key=", sent_req.full_url)
        self.assertNotIn("synthetic_fake_key", sent_req.full_url)
        self.assertEqual(sent_req.get_header("X-goog-api-key"), "synthetic_fake_key")

    @patch("urllib.request.urlopen")
    def test_handles_markdown_wrapped_json(self, mock_urlopen):
        """Verify markdown code block wrappers (```json ... ```) are cleanly stripped."""
        wrapped_json = "```json\n{\"project_summary\": \"Markdown wrapped\"}\n```"
        mock_payload = {
            "candidates": [
                {
                    "content": {"parts": [{"text": wrapped_json}]},
                    "finishReason": "STOP",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = GeminiClient(api_key="synthetic_key")
        result = client.generate_structured_json("Prompt")
        self.assertEqual(result["project_summary"], "Markdown wrapped")

    @patch("urllib.request.urlopen")
    def test_quota_error_429(self, mock_urlopen):
        """Verify HTTP 429 raises GeminiQuotaError."""
        http_err = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com",
            code=429,
            msg="Resource Exhausted",
            hdrs={},
            fp=BytesIO(b'{"error": {"message": "Resource has been exhausted"}}'),
        )
        mock_urlopen.side_effect = http_err

        client = GeminiClient(api_key="synthetic_key")
        with self.assertRaises(GeminiQuotaError):
            client.generate_structured_json("Prompt")

    @patch("urllib.request.urlopen")
    def test_model_not_found_404(self, mock_urlopen):
        """Verify HTTP 404 raises GeminiModelNotFoundError."""
        http_err = urllib.error.HTTPError(
            url="https://generativelanguage.googleapis.com",
            code=404,
            msg="Not Found",
            hdrs={},
            fp=BytesIO(b'{"error": {"message": "Model not found"}}'),
        )
        mock_urlopen.side_effect = http_err

        client = GeminiClient(api_key="synthetic_key", model="invalid-model-name")
        with self.assertRaises(GeminiModelNotFoundError):
            client.generate_structured_json("Prompt")

    @patch("urllib.request.urlopen")
    def test_malformed_json_raises_response_error(self, mock_urlopen):
        """Verify non-JSON response raises GeminiResponseError."""
        mock_payload = {
            "candidates": [
                {
                    "content": {"parts": [{"text": "I am not a JSON object."}]},
                    "finishReason": "STOP",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = GeminiClient(api_key="synthetic_key")
        with self.assertRaises(GeminiResponseError):
            client.generate_structured_json("Prompt")

    @patch("urllib.request.urlopen")
    def test_request_body_structured_output_schema_placement(self, mock_urlopen):
        """Verify request body structure, responseMimeType, and responseSchema placement in generationConfig."""
        mock_payload = {
            "candidates": [
                {
                    "content": {"parts": [{"text": json.dumps({"project_summary": "Schema verified"})}]},
                    "finishReason": "STOP",
                }
            ]
        }
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(mock_payload).encode("utf-8")
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        client = GeminiClient(api_key="synthetic_test_key", model="gemini-3.8-flash")
        sample_schema = {
            "type": "object",
            "properties": {"project_summary": {"type": "string"}},
            "required": ["project_summary"],
        }

        result = client.generate_structured_json(
            prompt="Analyze repository context",
            system_instruction="Strict JSON output only",
            temperature=0.1,
            response_schema=sample_schema,
        )

        self.assertEqual(result["project_summary"], "Schema verified")

        # Inspect exact outbound request payload sent via urllib
        sent_req = mock_urlopen.call_args[0][0]
        sent_body = json.loads(sent_req.data.decode("utf-8"))

        # Verify generationConfig placement
        self.assertIn("generationConfig", sent_body)
        gen_cfg = sent_body["generationConfig"]
        self.assertEqual(gen_cfg.get("responseMimeType"), "application/json")
        self.assertEqual(gen_cfg.get("temperature"), 0.1)
        self.assertEqual(gen_cfg.get("responseSchema"), sample_schema)

        # Verify contents and system instruction
        self.assertEqual(sent_body["contents"][0]["parts"][0]["text"], "Analyze repository context")
        self.assertEqual(sent_body["systemInstruction"]["parts"][0]["text"], "Strict JSON output only")
        self.assertEqual(sent_req.get_header("X-goog-api-key"), "synthetic_test_key")


if __name__ == "__main__":
    unittest.main()
