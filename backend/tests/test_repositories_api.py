"""Unit tests for repository and ingestion API routes via ASGI."""

import asyncio
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.core.database import init_db
from app.integrations.github import GitHubClient, GitHubNotFoundError
from app.main import app
from app.services.ingestion import IngestionService


class TestRepositoriesAPI(unittest.TestCase):
    """Test suite for /api/repositories endpoints."""

    def setUp(self):
        """Configure clean temporary test database."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_api.db"

        self.db_patcher = patch("app.core.database.get_db_path", return_value=self.db_path)
        self.db_patcher.start()
        init_db(self.db_path)

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

        # Extract query string if present
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

    @patch("app.services.ingestion.GitHubClient")
    def test_connect_repository_success_and_validation(self, mock_client_cls):
        """Verify repository connection and URL validation."""
        mock_instance = MagicMock()
        mock_instance.get_repository.return_value = {
            "external_id": "112233",
            "name": "fastapi",
            "full_name": "tiangolo/fastapi",
            "description": "FastAPI framework",
            "default_branch": "master",
            "repository_url": "https://github.com/tiangolo/fastapi",
        }
        mock_client_cls.return_value = mock_instance

        # 1. Successful connection
        status_code, body = asyncio.run(
            self._dispatch_request("POST", "/api/repositories/connect", {"repository_url": "https://github.com/tiangolo/fastapi"})
        )
        self.assertEqual(status_code, 201)
        self.assertEqual(body["full_name"], "tiangolo/fastapi")
        self.assertIn("id", body)

        # 2. Invalid URL domain rejected
        status_code, body = asyncio.run(
            self._dispatch_request("POST", "/api/repositories/connect", {"repository_url": "https://gitlab.com/owner/repo"})
        )
        self.assertEqual(status_code, 400)
        self.assertIn("detail", body)

    @patch("app.services.ingestion.GitHubClient")
    def test_ingest_and_query_sources(self, mock_client_cls):
        """Verify full repository connect -> ingest -> sources & activity flow."""
        mock_instance = MagicMock()
        mock_instance.get_repository.return_value = {
            "external_id": "445566",
            "name": "project-x",
            "full_name": "team/project-x",
            "description": "Project X",
            "default_branch": "main",
            "repository_url": "https://github.com/team/project-x",
        }
        mock_instance.get_commits.return_value = [
            {"commit_hash": "c1", "message": "feat: init", "author_name": "bob", "timestamp": "2026-11-01T00:00:00Z"}
        ]
        mock_instance.get_issues.return_value = []
        mock_instance.get_pull_requests.return_value = []
        mock_client_cls.return_value = mock_instance

        # Connect
        _, connect_res = asyncio.run(
            self._dispatch_request("POST", "/api/repositories/connect", {"repository_url": "https://github.com/team/project-x"})
        )
        repo_id = connect_res["id"]

        # Ingest
        status_code, ingest_res = asyncio.run(
            self._dispatch_request("POST", f"/api/repositories/{repo_id}/ingest")
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(ingest_res["status"], "completed")
        self.assertEqual(ingest_res["chunks_created"], 1)

        # Query sources
        status_code, sources_res = asyncio.run(
            self._dispatch_request("GET", f"/api/repositories/{repo_id}/sources")
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(sources_res["total"], 1)
        chunk_id = sources_res["sources"][0]["id"]
        self.assertEqual(sources_res["sources"][0]["commit_hash"], "c1")

        # Query single source chunk by ID
        status_code, single_source_res = asyncio.run(
            self._dispatch_request("GET", f"/api/repositories/{repo_id}/sources/{chunk_id}")
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(single_source_res["id"], chunk_id)
        self.assertEqual(single_source_res["commit_hash"], "c1")

        # Query activity timeline
        status_code, activity_res = asyncio.run(
            self._dispatch_request("GET", f"/api/repositories/{repo_id}/activity")
        )
        self.assertEqual(status_code, 200)
        self.assertEqual(len(activity_res), 1)
        self.assertEqual(activity_res[0]["title"], "feat: init")

    @patch("app.services.ingestion.GitHubClient")
    def test_get_source_chunk_cross_repository_rejection(self, mock_client_cls):
        """Verify requesting a source chunk using an unauthorized/different repository ID returns 404."""
        mock_client = MagicMock()
        mock_client.get_repository.return_value = {
            "name": "project-a",
            "full_name": "team/project-a",
            "default_branch": "main",
            "description": "Repo A",
            "html_url": "https://github.com/team/project-a",
        }
        mock_client.get_commits.return_value = [
            {"commit_hash": "c_a", "message": "feat: in repo a", "author_name": "dev", "timestamp": "2026-01-01T00:00:00Z"}
        ]
        mock_client.get_issues.return_value = []
        mock_client.get_pull_requests.return_value = []
        mock_client_cls.return_value = mock_client

        # Connect and ingest Repo A
        _, connect_a = asyncio.run(
            self._dispatch_request("POST", "/api/repositories/connect", {"repository_url": "https://github.com/team/project-a"})
        )
        repo_a_id = connect_a["id"]
        asyncio.run(self._dispatch_request("POST", f"/api/repositories/{repo_a_id}/ingest"))

        # Fetch Repo A chunk ID
        _, sources_a = asyncio.run(self._dispatch_request("GET", f"/api/repositories/{repo_a_id}/sources"))
        chunk_a_id = sources_a["sources"][0]["id"]

        # Connect Repo B
        mock_client.get_repository.return_value = {
            "name": "project-b",
            "full_name": "team/project-b",
            "default_branch": "main",
            "description": "Repo B",
            "html_url": "https://github.com/team/project-b",
        }
        _, connect_b = asyncio.run(
            self._dispatch_request("POST", "/api/repositories/connect", {"repository_url": "https://github.com/team/project-b"})
        )
        repo_b_id = connect_b["id"]

        # 1. Attempt cross-repo access: request chunk_a_id via repo_b URL
        status_code, body = asyncio.run(
            self._dispatch_request("GET", f"/api/repositories/{repo_b_id}/sources/{chunk_a_id}")
        )
        self.assertEqual(status_code, 404)
        self.assertIn("not found in repository", body.get("detail", "").lower())

        # 2. Attempt non-existent chunk ID lookup
        status_code, body = asyncio.run(
            self._dispatch_request("GET", f"/api/repositories/{repo_a_id}/sources/non_existent_chunk_123")
        )
        self.assertEqual(status_code, 404)
        self.assertIn("not found in repository", body.get("detail", "").lower())


if __name__ == "__main__":
    unittest.main()
