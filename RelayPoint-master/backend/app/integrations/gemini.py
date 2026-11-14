"""Lightweight Google Gemini REST API Client.

Uses Python standard-library urllib.request to interact with the Gemini API,
enforcing JSON structured outputs, connection timeouts, and bounded retries.
"""

import json
import logging
import time
from typing import Any, Dict, Optional
import urllib.error
import urllib.parse
import urllib.request

from app.core.config import get_settings

logger = logging.getLogger("relaypoint.gemini")

GEMINI_API_HOST = "https://generativelanguage.googleapis.com/v1beta/models"


class GeminiError(Exception):
    """Base exception for Gemini operations."""
    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class GeminiAuthError(GeminiError):
    """Raised when API key is missing, unauthorized, or invalid."""
    pass


class GeminiQuotaError(GeminiError):
    """Raised when quota or rate limits are exceeded (HTTP 429)."""
    pass


class GeminiModelNotFoundError(GeminiError):
    """Raised when the specified model does not exist or is unavailable."""
    pass


class GeminiResponseError(GeminiError):
    """Raised when the model response is malformed, blocked, or not valid JSON."""
    pass


class GeminiClient:
    """Client for generating grounded structured knowledge from Gemini models."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
    ):
        settings = get_settings()
        if api_key is None and settings.GEMINI_API_KEY:
            self._api_key = settings.GEMINI_API_KEY.get_secret_value().strip()
        else:
            self._api_key = api_key.strip() if api_key else None

        self._model = model or settings.GEMINI_MODEL
        self._timeout = timeout or settings.GEMINI_REQUEST_TIMEOUT
        self._max_retries = max_retries if max_retries is not None else settings.GEMINI_MAX_RETRIES

    @property
    def is_configured(self) -> bool:
        """Return True if an API key is available."""
        return bool(self._api_key)

    def generate_structured_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Send a prompt to Gemini requesting structured JSON output.
        
        Args:
            prompt: User prompt content containing bounded repository context.
            system_instruction: Optional high-level system directives.
            temperature: Sampling temperature (low for deterministic factual synthesis).
            response_schema: Optional native JSON schema to enforce on the Gemini output.
            
        Returns:
            Parsed JSON object as a Python dict.
            
        Raises:
            GeminiAuthError on missing/invalid credentials.
            GeminiQuotaError on quota limits.
            GeminiResponseError on malformed output.
        """
        if not self._api_key:
            raise GeminiAuthError(
                "GEMINI_API_KEY is not configured. Please set a valid API key in your environment or .env file."
            )

        endpoint_url = f"{GEMINI_API_HOST}/{self._model}:generateContent"

        gen_config: Dict[str, Any] = {
            "responseMimeType": "application/json",
            "temperature": temperature,
        }
        if response_schema:
            gen_config["responseSchema"] = response_schema

        request_body: Dict[str, Any] = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}],
                }
            ],
            "generationConfig": gen_config,
        }

        if system_instruction:
            request_body["systemInstruction"] = {
                "parts": [{"text": system_instruction}],
            }

        post_data = json.dumps(request_body).encode("utf-8")

        req = urllib.request.Request(
            url=endpoint_url,
            data=post_data,
            method="POST",
            headers={
                "Content-Type": "application/json",
                "User-Agent": "RelayPoint-MVP",
                "x-goog-api-key": self._api_key,
            },
        )

        last_error = None
        for attempt in range(self._max_retries + 1):
            try:
                with urllib.request.urlopen(req, timeout=self._timeout) as resp:
                    resp_bytes = resp.read()
                    data = json.loads(resp_bytes.decode("utf-8"))
                    return self._extract_json_payload(data)

            except urllib.error.HTTPError as http_err:
                code = http_err.code
                last_error = http_err

                # Do NOT retry permanent client errors
                if code in (401, 403):
                    raise GeminiAuthError("Gemini API key is invalid or unauthorized.") from http_err
                elif code == 429:
                    raise GeminiQuotaError("Gemini API rate limit or quota exceeded.") from http_err
                elif code == 404:
                    raise GeminiModelNotFoundError(
                        f"Configured Gemini model '{self._model}' was not found. Check GEMINI_MODEL setting."
                    ) from http_err

                # Retry transient 5xx errors with backoff
                if code >= 500 and attempt < self._max_retries:
                    backoff = 1.0 * (2 ** attempt)
                    logger.warning("Gemini 5xx error (attempt %d). Retrying in %.1fs...", attempt + 1, backoff)
                    time.sleep(backoff)
                    continue

                raise GeminiError(f"Gemini API request failed with HTTP {code}.", status_code=code) from http_err

            except urllib.error.URLError as url_err:
                last_error = url_err
                if attempt < self._max_retries:
                    time.sleep(1.0)
                    continue
                raise GeminiError(f"Network error communicating with Gemini API: {url_err.reason}") from url_err

            except TimeoutError as timeout_err:
                last_error = timeout_err
                if attempt < self._max_retries:
                    time.sleep(1.0)
                    continue
                raise GeminiError(f"Gemini API request timed out after {self._timeout}s.") from timeout_err

        raise GeminiError(f"Gemini request failed after {self._max_retries} retries: {last_error}")

    def _extract_json_payload(self, response_data: Dict[str, Any]) -> Dict[str, Any]:
        """Extract and parse the JSON string from Gemini's candidate output structure."""
        candidates = response_data.get("candidates")
        if not candidates:
            feedback = response_data.get("promptFeedback", {})
            block_reason = feedback.get("blockReason", "Unknown")
            raise GeminiResponseError(f"Gemini did not return any candidate outputs. Reason: {block_reason}")

        first_candidate = candidates[0]
        finish_reason = first_candidate.get("finishReason")
        if finish_reason in ("SAFETY", "RECITATION"):
            raise GeminiResponseError(f"Gemini output was blocked due to: {finish_reason}")

        content_parts = first_candidate.get("content", {}).get("parts", [])
        if not content_parts:
            raise GeminiResponseError("Gemini response candidate contains no content parts.")

        text_content = content_parts[0].get("text", "").strip()
        if not text_content:
            raise GeminiResponseError("Gemini candidate content part is empty.")

        # Clean any potential leading/trailing markdown code ticks if returned
        if text_content.startswith("```json"):
            text_content = text_content[7:]
        elif text_content.startswith("```"):
            text_content = text_content[3:]
        if text_content.endswith("```"):
            text_content = text_content[:-3]
        text_content = text_content.strip()

        try:
            parsed = json.loads(text_content)
            if not isinstance(parsed, dict):
                raise GeminiResponseError(f"Expected JSON object from model, received {type(parsed).__name__}.")
            return parsed
        except json.JSONDecodeError as decode_err:
            raise GeminiResponseError(
                f"Gemini output was not valid JSON: {decode_err.msg}. Preview: {text_content[:200]}"
            ) from decode_err
