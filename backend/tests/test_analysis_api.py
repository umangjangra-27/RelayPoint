"""Unit tests for AI analysis and report API endpoints via ASGI."""

import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.core.database import get_db_context, init_db
from app.integrations.gemini import (
    GeminiAuthError,
    GeminiModelNotFoundError,
    GeminiQuotaError,
)
from app.main import app
from app.schemas.analysis import (
    AnalysisResult,
    CoverageSummary,
    Finding,
    FindingCategory,
)


class TestAnalysisAPI(unittest.TestCase):
    """Test suite for /api/repositories/.../analyze and /api/reports endpoints."""

    def setUp(self):
        """Set up isolated test database and seed repository with source chunk."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_analysis_api.db"

        self.db_patcher = patch("app.core.database.get_db_path", return_value=self.db_path)
        self.db_patcher.start()
        init_db(self.db_path)

        with get_db_context() as conn:
            conn.execute(
                """
                INSERT INTO repositories (id, provider, name, full_name, default_branch, repository_url, created_at, updated_at)
                VALUES ('repo_api_test', 'github', 'demo', 'org/demo', 'main', 'https://github.com/org/demo', '2026-01-01', '2026-01-01');
                """
            )
            conn.execute(
                """
                INSERT INTO source_chunks (id, repository_id, source_type, source_external_id, commit_hash, content, content_hash, source_url, created_at)
                VALUES ('chunk_api_1', 'repo_api_test', 'commit', 'hash01', 'hash01', 'feat: core engine setup', 'hash_val', 'http://example.com', '2026-01-01');
                """
            )

    def tearDown(self):
        """Clean up test resources."""
        self.db_patcher.stop()
        self.temp_dir.cleanup()

    async def _dispatch_request(self, method: str, path: str, body: dict = None) -> tuple[int, dict]:
        """Dispatch ASGI request directly to FastAPI app."""
        body_bytes = json.dumps(body).encode("utf-8") if body is not None else b""
        headers = [
            (b"host", b"localhost"),
            (b"content-type", b"application/json"),
            (b"content-length", str(len(body_bytes)).encode("ascii")),
        ]

        raw_path = path
        query_string = b""
        if "?" in path:
            raw_path, qs = path.split("?", 1)
            query_string = qs.encode("utf-8")

        scope = {
            "type": "http",
            "http_version": "1.1",
            "method": method.upper(),
            "path": raw_path,
            "raw_path": raw_path.encode("utf-8"),
            "query_string": query_string,
            "headers": headers,
            "client": ("127.0.0.1", 8000),
            "server": ("127.0.0.1", 8000),
        }
        messages = []

        async def receive():
            return {"type": "http.request", "body": body_bytes, "more_body": False}

        async def send(msg):
            messages.append(msg)

        await app(scope, receive, send)

        start_msg = next(m for m in messages if m["type"] == "http.response.start")
        body_parts = [m.get("body", b"") for m in messages if m["type"] == "http.response.body"]
        raw_body = b"".join(body_parts).decode("utf-8")
        try:
            payload = json.loads(raw_body)
        except Exception:
            payload = {"raw": raw_body}

        return start_msg["status"], payload

    def test_analyze_non_existent_repo_404(self):
        """Verify analyzing an unknown repository ID returns 404."""
        status_code, body = asyncio.run(
            self._dispatch_request("POST", "/api/repositories/repo_non_existent/analyze")
        )
        self.assertEqual(status_code, 404)
        self.assertIn("not found", body.get("detail", "").lower())

    def test_analyze_repo_with_no_sources_400(self):
        """Verify analyzing a repository with 0 ingested chunks returns 400."""
        with get_db_context() as conn:
            conn.execute(
                """
                INSERT INTO repositories (id, provider, name, full_name, default_branch, repository_url, created_at, updated_at)
                VALUES ('repo_empty', 'github', 'empty', 'org/empty', 'main', 'https://github.com/org/empty', '2026-01-01', '2026-01-01');
                """
            )

        status_code, body = asyncio.run(
            self._dispatch_request("POST", "/api/repositories/repo_empty/analyze")
        )
        self.assertEqual(status_code, 400)
        self.assertIn("no ingested source chunks", body.get("detail", "").lower())

    @patch("app.services.analyzer.GeminiClient")
    def test_successful_analysis_and_report_retrieval(self, mock_gemini_cls):
        """Verify full flow: analyze -> list reports -> get report -> reverify."""
        mock_instance = MagicMock()
        mock_instance.is_configured = True
        mock_instance.generate_structured_json.return_value = {
            "project_summary": "Synthesized project narrative.",
            "architectural_decisions": [
                {
                    "id": "arch_1",
                    "category": "architectural_decision",
                    "title": "Clean Architecture",
                    "description": "Layered design without heavy ORM.",
                    "priority": "high",
                    "confidence": "high",
                    "evidence_source_ids": ["chunk_api_1"],
                    "evidence_explanation": "Initial commit setup.",
                }
            ],
            "active_workstreams": [],
            "unfinished_work": [],
            "blockers": [],
            "technical_risks": [],
            "fragile_modules": [],
            "continuation_roadmap": [],
            "uncertainties": [],
            "evidence_references": ["chunk_api_1"],
        }
        mock_gemini_cls.return_value = mock_instance

        # 1. Trigger Analysis
        status_code, analyze_res = asyncio.run(
            self._dispatch_request("POST", "/api/repositories/repo_api_test/analyze")
        )
        self.assertEqual(status_code, 201)
        self.assertIn("report_id", analyze_res)
        report_id = analyze_res["report_id"]

        # 2. List Reports
        status_code, reports_list = asyncio.run(
            self._dispatch_request("GET", "/api/repositories/repo_api_test/reports")
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(len(reports_list), 1)
        self.assertEqual(reports_list[0]["id"], report_id)

        # 3. Retrieve Report Detail
        status_code, report_detail = asyncio.run(
            self._dispatch_request("GET", f"/api/reports/{report_id}")
        )
        self.assertEqual(status_code, 200)
        self.assertIn("report_data", report_detail)
        payload = report_detail["report_data"]
        self.assertIn("developer_view", payload)
        self.assertIn("team_lead_view", payload)

        # 4. Re-verify Report
        status_code, verify_res = asyncio.run(
            self._dispatch_request("POST", f"/api/reports/{report_id}/verify")
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(verify_res["status"], "reverified")

    def test_get_non_existent_report_404(self):
        """Verify requesting an unknown report ID returns 404."""
        status_code, body = asyncio.run(
            self._dispatch_request("GET", "/api/reports/rep_non_existent_999")
        )
        self.assertEqual(status_code, 404)
        self.assertIn("not found", body.get("detail", "").lower())

    def test_reverify_non_existent_report_404(self):
        """Verify re-verifying an unknown report ID returns 404."""
        status_code, body = asyncio.run(
            self._dispatch_request("POST", "/api/reports/rep_non_existent_999/verify")
        )
        self.assertEqual(status_code, 404)
        self.assertIn("not found", body.get("detail", "").lower())

    def test_list_reports_non_existent_repo_404(self):
        """Verify listing reports for an unknown repository ID returns 404."""
        status_code, body = asyncio.run(
            self._dispatch_request("GET", "/api/repositories/repo_ghost/reports")
        )
        self.assertEqual(status_code, 404)
        self.assertIn("not found", body.get("detail", "").lower())

    @patch("app.services.analyzer.GeminiClient")
    def test_analysis_gemini_auth_error_401(self, mock_gemini_cls):
        """Verify Gemini authentication failure maps to HTTP 401."""
        mock_instance = MagicMock()
        mock_instance.is_configured = True
        mock_instance.generate_structured_json.side_effect = GeminiAuthError("Invalid Gemini API key.")
        mock_gemini_cls.return_value = mock_instance

        status_code, body = asyncio.run(
            self._dispatch_request("POST", "/api/repositories/repo_api_test/analyze")
        )
        self.assertEqual(status_code, 401)
        self.assertIn("invalid gemini api key", body.get("detail", "").lower())

    @patch("app.services.analyzer.GeminiClient")
    def test_analysis_gemini_quota_error_429(self, mock_gemini_cls):
        """Verify Gemini quota/rate-limit error maps to HTTP 429."""
        mock_instance = MagicMock()
        mock_instance.is_configured = True
        mock_instance.generate_structured_json.side_effect = GeminiQuotaError("Resource exhausted.")
        mock_gemini_cls.return_value = mock_instance

        status_code, body = asyncio.run(
            self._dispatch_request("POST", "/api/repositories/repo_api_test/analyze")
        )
        self.assertEqual(status_code, 429)
        self.assertIn("resource exhausted", body.get("detail", "").lower())

    @patch("app.services.analyzer.GeminiClient")
    def test_analysis_gemini_model_not_found_404(self, mock_gemini_cls):
        """Verify Gemini model-not-found error maps to HTTP 404."""
        mock_instance = MagicMock()
        mock_instance.is_configured = True
        mock_instance.generate_structured_json.side_effect = GeminiModelNotFoundError(
            "Configured Gemini model 'gemini-2.5-flash' was not found. Check GEMINI_MODEL setting."
        )
        mock_gemini_cls.return_value = mock_instance

        status_code, body = asyncio.run(
            self._dispatch_request("POST", "/api/repositories/repo_api_test/analyze")
        )
        self.assertEqual(status_code, 404)
        self.assertIn("not found", body.get("detail", "").lower())
        self.assertIn("gemini_model", body.get("detail", "").lower())


if __name__ == "__main__":
    unittest.main()
