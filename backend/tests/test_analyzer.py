"""Unit tests for the repository intelligence and bounded context analyzer."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.core.database import get_db_context, init_db
from app.integrations.gemini import GeminiClient, GeminiError
from app.services.analyzer import RepositoryAnalyzer, rank_and_bound_sources


class TestRepositoryAnalyzer(unittest.TestCase):
    """Test suite for bounded context preparation and AI analysis."""

    def setUp(self):
        """Configure isolated SQLite test database."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_analyzer.db"

        self.db_patcher = patch("app.core.database.get_db_path", return_value=self.db_path)
        self.db_patcher.start()
        init_db(self.db_path)

        # Mock Gemini Client
        self.mock_gemini = MagicMock(spec=GeminiClient)
        self.mock_gemini.is_configured = True
        self.analyzer = RepositoryAnalyzer(gemini_client=self.mock_gemini)

    def tearDown(self):
        """Clean up test resources."""
        self.db_patcher.stop()
        self.temp_dir.cleanup()

    def test_rank_and_bound_sources_prioritization(self):
        """Verify open PRs and issues take priority over older commits or closed items."""
        sources = [
            {"id": "chunk_closed_issue", "source_type": "issue", "content": "Closed bug", "metadata": {"state": "closed"}},
            {"id": "chunk_commit", "source_type": "commit", "content": "Recent commit", "metadata": {"timestamp": "2026-11-10T00:00:00Z"}},
            {"id": "chunk_open_pr", "source_type": "pull_request", "content": "Active PR", "metadata": {"state": "open"}},
            {"id": "chunk_open_issue", "source_type": "issue", "content": "Active blocker", "metadata": {"state": "open"}},
        ]

        # Allow only 2 chunks
        selected, coverage = rank_and_bound_sources(sources, max_chunks=2, max_chars=10000)

        self.assertEqual(len(selected), 2)
        # First two selected must be the open PR and open issue
        selected_types = [s["source_type"] for s in selected]
        self.assertIn("pull_request", selected_types)
        self.assertIn("issue", selected_types)
        self.assertFalse(coverage.is_complete_coverage)
        self.assertEqual(coverage.coverage_percentage, 50.0)

    def test_context_char_budget_enforcement(self):
        """Verify context packing stops when maximum character budget is reached."""
        sources = [
            {"id": f"chunk_{i}", "source_type": "commit", "content": "A" * 500, "metadata": {}}
            for i in range(10)
        ]

        # Budget allows ~2 chunks
        selected, coverage = rank_and_bound_sources(sources, max_chunks=10, max_chars=1200)
        self.assertLess(len(selected), 10)
        self.assertFalse(coverage.is_complete_coverage)

    def test_empty_repository_raises_error(self):
        """Verify analyzing a repository with no chunks raises ValueError."""
        with self.assertRaises(ValueError):
            self.analyzer.analyze_repository("non_existent_repo_id")

    def test_unconfigured_gemini_raises_error(self):
        """Verify calling analyze_repository when Gemini is not configured raises GeminiError."""
        self.mock_gemini.is_configured = False
        with self.assertRaises(GeminiError):
            self.analyzer.analyze_repository("some_repo_id")

    def test_successful_analysis_schema_parsing(self):
        """Verify valid Gemini output parses cleanly into AnalysisResult."""
        # Insert a sample repository and chunk
        with get_db_context() as conn:
            conn.execute(
                """
                INSERT INTO repositories (id, provider, name, full_name, default_branch, repository_url, created_at, updated_at)
                VALUES ('repo_1', 'github', 'test', 'owner/test', 'main', 'https://github.com/owner/test', '2026-01-01', '2026-01-01');
                """
            )
            conn.execute(
                """
                INSERT INTO source_chunks (id, repository_id, source_type, content, content_hash, created_at)
                VALUES ('chunk_1', 'repo_1', 'commit', 'Initial commit', 'hash1', '2026-01-01');
                """
            )

        # Mock structured output from Gemini
        self.mock_gemini.generate_structured_json.return_value = {
            "project_summary": "RelayPoint knowledge platform project.",
            "architectural_decisions": [
                {
                    "id": "arch_01",
                    "category": "architectural_decision",
                    "title": "SQLite Embedded Database",
                    "description": "Selected SQLite for local persistence without daemon overhead.",
                    "priority": "high",
                    "confidence": "high",
                    "evidence_source_ids": ["chunk_1"],
                    "evidence_explanation": "Commit message references SQLite setup.",
                }
            ],
            "active_workstreams": [],
            "unfinished_work": [],
            "blockers": [],
            "technical_risks": [],
            "fragile_modules": ["backend/app/main.py"],
            "continuation_roadmap": [],
            "uncertainties": ["Deployment environment unspecified."],
            "evidence_references": ["chunk_1"],
        }

        result, selected = self.analyzer.analyze_repository("repo_1")
        self.assertEqual(result.project_summary, "RelayPoint knowledge platform project.")
        self.assertEqual(len(result.architectural_decisions), 1)
        self.assertEqual(result.architectural_decisions[0].id, "arch_01")
        self.assertTrue(result.coverage_summary.is_complete_coverage)


if __name__ == "__main__":
    unittest.main()
