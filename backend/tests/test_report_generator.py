"""Unit tests for handover report assembly, dual role views, and persistence."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.core.database import get_db_context, init_db
from app.schemas.analysis import (
    AnalysisResult,
    ConfidenceLevel,
    CoverageSummary,
    Finding,
    FindingCategory,
    PriorityLevel,
)
from app.services.report_generator import (
    ReportGenerator,
    get_report_by_id,
    list_reports_for_repository,
    reverify_report,
)


class TestReportGenerator(unittest.TestCase):
    """Test suite for report generation and role-tailored view synthesis."""

    def setUp(self):
        """Create temporary test database and seed repository with verified chunk."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_reports.db"

        self.db_patcher = patch("app.core.database.get_db_path", return_value=self.db_path)
        self.db_patcher.start()
        init_db(self.db_path)

        with get_db_context() as conn:
            conn.execute(
                """
                INSERT INTO repositories (id, provider, name, full_name, default_branch, repository_url, created_at, updated_at)
                VALUES ('repo_123', 'github', 'test-app', 'org/test-app', 'main', 'https://github.com/org/test-app', '2026-01-01', '2026-01-01');
                """
            )
            conn.execute(
                """
                INSERT INTO analysis_runs (id, repository_id, status, started_at)
                VALUES ('run_123', 'repo_123', 'running', '2026-01-01');
                """
            )
            conn.execute(
                """
                INSERT INTO source_chunks (id, repository_id, source_type, source_external_id, commit_hash, content, content_hash, source_url, created_at)
                VALUES ('chunk_123', 'repo_123', 'commit', 'abc1234', 'abc1234', 'feat: initial architecture setup', '864f1d431c172d733157e841f3d8f7663cb64e8b38eb158e23f03b573a903ce8', 'https://github.com/org/test-app/commit/abc1234', '2026-01-01');
                """
            )

        self.generator = ReportGenerator(repo_id="repo_123")

    def tearDown(self):
        """Clean up test resources."""
        self.db_patcher.stop()
        self.temp_dir.cleanup()

    def test_assemble_and_persist_report(self):
        """Verify report creation, dual view assembly, and SQLite persistence."""
        finding = Finding(
            id="find_01",
            category=FindingCategory.ARCHITECTURAL_DECISION,
            title="FastAPI Web Framework",
            description="FastAPI selected for asynchronous backend endpoints.",
            priority=PriorityLevel.HIGH,
            confidence=ConfidenceLevel.HIGH,
            evidence_source_ids=["chunk_123"],
            evidence_explanation="Architecture commit references FastAPI.",
        )

        coverage = CoverageSummary(
            total_available_chunks=1,
            analyzed_chunks=1,
            is_complete_coverage=True,
            coverage_percentage=100.0,
        )

        analysis = AnalysisResult(
            project_summary="A knowledge handover system built with FastAPI.",
            architectural_decisions=[finding],
            active_workstreams=[],
            unfinished_work=[],
            blockers=[],
            technical_risks=[],
            fragile_modules=["backend/app/main.py"],
            continuation_roadmap=[],
            uncertainties=["Frontend state management library unconfirmed."],
            evidence_references=["chunk_123"],
            coverage_summary=coverage,
        )

        result = self.generator.assemble_and_persist_report(
            analysis=analysis,
            analysis_run_id="run_123",
            repository_name="org/test-app",
            model_used="gemini-2.5-flash",
        )

        report_id = result["report_id"]
        self.assertTrue(report_id.startswith("rep_"))

        # 1. Retrieve full report
        stored_report = get_report_by_id(report_id)
        self.assertIsNotNone(stored_report)
        payload = stored_report["report_data"]

        # 2. Verify Developer View
        dev_view = payload["developer_view"]
        self.assertEqual(len(dev_view["technical_architecture"]), 1)
        self.assertEqual(dev_view["technical_architecture"][0]["title"], "FastAPI Web Framework")
        self.assertEqual(dev_view["fragile_files"], ["backend/app/main.py"])
        self.assertEqual(len(dev_view["evidence_appendix"]), 1)

        # 3. Verify Team Lead View
        lead_view = payload["team_lead_view"]
        self.assertIn("FastAPI", lead_view["executive_summary"])
        self.assertIn("Healthy", lead_view["project_health_status"])
        self.assertEqual(len(lead_view["uncertainties_and_open_questions"]), 1)

        # 4. Verify SQLite evidence_references persistence
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT count(*) FROM evidence_references WHERE analysis_run_id = 'run_123';")
            ev_count = cursor.fetchone()[0]
            self.assertEqual(ev_count, 1)

        # 5. Verify list summaries
        summaries = list_reports_for_repository("repo_123")
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["id"], report_id)

        # 6. Test reverification
        reverify_res = reverify_report(report_id)
        self.assertEqual(reverify_res["status"], "reverified")
        self.assertIn("verification_stats", reverify_res)


if __name__ == "__main__":
    unittest.main()
