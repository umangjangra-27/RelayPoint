"""Unit tests for the health endpoint and API routing."""

import asyncio
import json
import unittest
from unittest.mock import patch

from app.api.health import HealthResponse, get_health
from app.main import app


class TestHealthEndpoint(unittest.TestCase):
    """Test suite for backend health diagnostics."""

    def test_direct_health_function(self):
        """Verify the direct endpoint handler returns expected schema."""
        response = get_health()
        self.assertIsInstance(response, HealthResponse)
        self.assertIn(response.status, ("healthy", "degraded"))
        self.assertEqual(response.app_name, "RelayPoint")
        self.assertEqual(response.version, "0.1.0")
        self.assertIn(response.database, ("connected", "disconnected"))

    def test_health_degraded_when_db_down(self):
        """Verify endpoint reports degraded status when database fails probe."""
        with patch("app.api.health.check_db_health", return_value={"status": "error", "message": "Failed probe"}):
            response = get_health()
            self.assertEqual(response.status, "degraded")
            self.assertEqual(response.database, "disconnected")

    def test_asgi_http_health_request(self):
        """Verify end-to-end ASGI request dispatch to GET /api/health."""
        async def run_request():
            scope = {
                "type": "http",
                "http_version": "1.1",
                "method": "GET",
                "path": "/api/health",
                "raw_path": b"/api/health",
                "query_string": b"",
                "headers": [(b"host", b"localhost")],
                "client": ("127.0.0.1", 8000),
                "server": ("127.0.0.1", 8000),
            }
            messages = []

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            async def send(msg):
                messages.append(msg)

            await app(scope, receive, send)

            start_msg = next(m for m in messages if m["type"] == "http.response.start")
            body_parts = [m.get("body", b"") for m in messages if m["type"] == "http.response.body"]
            body = json.loads(b"".join(body_parts).decode("utf-8"))

            return start_msg["status"], body

        status_code, payload = asyncio.run(run_request())
        self.assertEqual(status_code, 200)
        self.assertIn("status", payload)
        self.assertEqual(payload["app_name"], "RelayPoint")
        self.assertEqual(payload["version"], "0.1.0")
        self.assertIn("database", payload)

        # Invariant: No file paths or sensitive keys in response payload
        payload_str = json.dumps(payload)
        self.assertNotIn("C:\\", payload_str)
        self.assertNotIn("/Users/", payload_str)
        self.assertNotIn("token", payload_str.lower())
        self.assertNotIn("secret", payload_str.lower())


if __name__ == "__main__":
    unittest.main()
