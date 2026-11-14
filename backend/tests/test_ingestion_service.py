"""Unit tests for the repository ingestion service and duplicate detection."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.core.database import get_db_context, init_db
from app.integrations.github import GitHubClient, GitHubError
from app.services.ingestion import IngestionService


class TestIngestionService(unittest.TestCase):
    """Test suite for repository history ingestion pipeline."""

    def setUp(self):
        """Create dedicated temporary SQLite database for testing."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_ingestion.db"

        # Patch get_db_path so IngestionService uses this temporary database
        self.db_patcher = patch("app.core.database.get_db_path", return_value=self.db_path)
        self.db_patcher.start()
        init_db(self.db_path)

        # Mock GitHub Client
        self.mock_github = MagicMock(spec=GitHubClient)
        self.mock_github.get_repository.return_value = {
            "external_id": "99999",
            "name": "mock-repo",
            "full_name": "owner/mock-repo",
            "description": "Mocked test repository",
            "default_branch": "main",
            "repository_url": "https://github.com/owner/mock-repo",
        }

        self.service = IngestionService(github_client=self.mock_github)

    def tearDown(self):
        """Clean up test resources."""
        self.db_patcher.stop()
        self.temp_dir.cleanup()

    def test_connect_repository(self):
        """Verify repository registration and idempotent lookup."""
        repo = self.service.connect_repository("https://github.com/owner/mock-repo")
        self.assertEqual(repo["full_name"], "owner/mock-repo")
        self.assertEqual(repo["default_branch"], "main")

        # Second connection returns same existing record
        repo_duplicate = self.service.connect_repository("https://github.com/owner/mock-repo")
        self.assertEqual(repo["id"], repo_duplicate["id"])

    def test_ingestion_sanitization_and_persistence(self):
        """Verify ingestion scrubs credentials before persisting source chunks."""
        repo = self.service.connect_repository("https://github.com/owner/mock-repo")
        repo_id = repo["id"]

        # Synthetic content with secrets
        synthetic_secret_commit = "fix: update auth flow with ghp_1234567890abcdefghijklmnopqrstuvwxyzAB"
        synthetic_secret_issue = "Bug Report\nFound leaked token AIzaSyFakeKeyGooglePayloadForTesting1 in client log"
        synthetic_secret_pr = "PR: update config\npassword = 'ProductionPassword999!'"

        self.mock_github.get_commits.return_value = [
            {
                "commit_hash": "c0ffee1234567890",
                "message": synthetic_secret_commit,
                "author_name": "Alice",
                "author_email": "alice@example.com",
                "timestamp": "2026-11-10T10:00:00Z",
                "source_url": "https://github.com/owner/mock-repo/commit/c0ffee1234567890",
            }
        ]
        self.mock_github.get_issues.return_value = [
            {
                "number": 42,
                "title": "Bug Report",
                "body": "Found leaked token AIzaSyFakeKeyGooglePayloadForTesting1 in client log",
                "state": "open",
                "author": "bob",
                "created_at": "2026-11-10T11:00:00Z",
                "closed_at": None,
                "labels": ["bug"],
                "source_url": "https://github.com/owner/mock-repo/issues/42",
            }
        ]
        self.mock_github.get_pull_requests.return_value = [
            {
                "number": 101,
                "title": "PR: update config",
                "body": "password = 'ProductionPassword999!'",
                "state": "closed",
                "author": "charlie",
                "created_at": "2026-11-10T12:00:00Z",
                "closed_at": "2026-11-10T13:00:00Z",
                "merged_at": "2026-11-10T13:00:00Z",
                "head_branch": "patch-1",
                "base_branch": "main",
                "source_url": "https://github.com/owner/mock-repo/pull/101",
            }
        ]

        # Execute ingestion
        result = self.service.ingest_repository(repo_id)
        self.assertEqual(result["status"], "completed")
        self.assertEqual(result["chunks_created"], 3)
        self.assertEqual(result["duplicates_skipped"], 0)

        # Inspect source chunks in database
        sources_resp = self.service.get_source_chunks(repo_id)
        self.assertEqual(sources_resp["total"], 3)

        for chunk in sources_resp["sources"]:
            content = chunk["content"]
            # CRITICAL: Raw secrets must NEVER be persisted
            self.assertNotIn("ghp_1234567890abcdefghijklmnopqrstuvwxyzAB", content)
            self.assertNotIn("AIzaSyFakeKeyGooglePayloadForTesting1", content)
            self.assertNotIn("ProductionPassword999!", content)
            self.assertIn("[REDACTED]", content)

    def test_duplicate_ingestion(self):
        """Verify repeated ingestion detects duplicate chunks and skips them without errors."""
        repo = self.service.connect_repository("https://github.com/owner/mock-repo")
        repo_id = repo["id"]

        self.mock_github.get_commits.return_value = [
            {"commit_hash": "sha100", "message": "Initial commit", "source_url": "http://example.com"}
        ]
        self.mock_github.get_issues.return_value = []
        self.mock_github.get_pull_requests.return_value = []

        # First run creates chunk
        res1 = self.service.ingest_repository(repo_id)
        self.assertEqual(res1["chunks_created"], 1)
        self.assertEqual(res1["duplicates_skipped"], 0)

        # Second run skips duplicate chunk
        res2 = self.service.ingest_repository(repo_id)
        self.assertEqual(res2["chunks_created"], 0)
        self.assertEqual(res2["duplicates_skipped"], 1)

    def test_activity_timeline_ordering(self):
        """Verify activity timeline gathers items and sorts descending by timestamp."""
        repo = self.service.connect_repository("https://github.com/owner/mock-repo")
        repo_id = repo["id"]

        self.mock_github.get_commits.return_value = [
            {
                "commit_hash": "sha1",
                "message": "Older commit",
                "author_name": "dev",
                "timestamp": "2026-11-01T00:00:00Z",
            }
        ]
        self.mock_github.get_issues.return_value = [
            {
                "number": 5,
                "title": "Newer issue",
                "body": "Issue details",
                "author": "tester",
                "created_at": "2026-11-02T00:00:00Z",
            }
        ]
        self.mock_github.get_pull_requests.return_value = []

        self.service.ingest_repository(repo_id)
        timeline = self.service.get_activity_timeline(repo_id)

        self.assertEqual(len(timeline), 2)
        # Most recent first
        self.assertEqual(timeline[0]["identifier"], "5")
        self.assertEqual(timeline[1]["identifier"], "sha1")


if __name__ == "__main__":
    unittest.main()
