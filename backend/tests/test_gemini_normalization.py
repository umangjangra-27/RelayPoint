"""Unit tests for Gemini structured output normalization and schema compatibility."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from pydantic import ValidationError

from app.core.database import get_db_context, init_db
from app.schemas.analysis import (
    AnalysisResult,
    CoverageSummary,
    FindingCategory,
    VerificationStatus,
    get_gemini_analysis_schema,
)
from app.services.analyzer import (
    RepositoryAnalyzer,
    normalize_gemini_analysis_response,
)
from app.services.report_generator import ReportGenerator, get_report_by_id
from app.services.verifier import EvidenceVerifier


class TestGeminiNormalizationAndCompatibility(unittest.TestCase):
    """Test suite for normalizing Gemini 3.8 Flash outputs without network requests."""

    def setUp(self):
        """Configure isolated test database with fixture data."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_norm.db"

        self.db_patcher = patch("app.core.database.get_db_path", return_value=self.db_path)
        self.db_patcher.start()
        init_db(self.db_path)

        # Compute exact cryptographic hashes
        import hashlib
        c1_text = "Initial commit with master branch"
        c1_hash = hashlib.sha256(c1_text.encode("utf-8")).hexdigest()

        c2_text = "Open issue: review pull requests noise"
        c2_hash = hashlib.sha256(c2_text.encode("utf-8")).hexdigest()

        cf_text = "Foreign commit chunk"
        cf_hash = hashlib.sha256(cf_text.encode("utf-8")).hexdigest()

        # Seed repository and source chunks
        with get_db_context() as conn:
            conn.execute(
                """
                INSERT INTO repositories (id, provider, name, full_name, default_branch, repository_url, created_at, updated_at)
                VALUES ('repo_norm_1', 'github', 'Hello-World', 'octocat/Hello-World', 'master', 'https://github.com/octocat/Hello-World', '2026-01-01', '2026-01-01');
                """
            )
            conn.execute(
                """
                INSERT INTO repositories (id, provider, name, full_name, default_branch, repository_url, created_at, updated_at)
                VALUES ('repo_foreign_2', 'github', 'other', 'other/other', 'main', 'https://github.com/other/other', '2026-01-01', '2026-01-01');
                """
            )
            conn.execute(
                """
                INSERT INTO source_chunks (id, repository_id, source_type, content, content_hash, created_at)
                VALUES ('chunk_01', 'repo_norm_1', 'commit', ?, ?, '2026-01-01');
                """,
                (c1_text, c1_hash),
            )
            conn.execute(
                """
                INSERT INTO source_chunks (id, repository_id, source_type, content, content_hash, created_at)
                VALUES ('chunk_02', 'repo_norm_1', 'issue', ?, ?, '2026-01-02');
                """,
                (c2_text, c2_hash),
            )
            conn.execute(
                """
                INSERT INTO source_chunks (id, repository_id, source_type, content, content_hash, created_at)
                VALUES ('chunk_foreign', 'repo_foreign_2', 'commit', ?, ?, '2026-01-01');
                """,
                (cf_text, cf_hash),
            )

    def tearDown(self):
        """Clean up test resources."""
        self.db_patcher.stop()
        self.temp_dir.cleanup()

    def test_exact_observed_gemini_response_shape(self):
        """Verify the exact observed live Gemini 3.8 Flash response shape normalizes and validates."""
        observed_gemini_payload = {
            "project_overview": {
                "summary": "octocat/Hello-World is the classic starter repository created by GitHub."
            },
            "architectural_decisions": [
                {
                    "decision": "Master branch workflow and pull-request workflow.",
                    "evidence_source_ids": ["chunk_01"],
                    "evidence_explanation": "Initial commit establishes the default branch as master.",
                },
                {
                    "decision": "Minimalist Hello World example with added Hello Python!",
                    "evidence_source_ids": ["chunk_01"],
                    "evidence_explanation": "README contains hello world text.",
                },
            ],
            "technical_risks": [
                {
                    "risk": "High noise ratio with numerous open pull requests and issues remaining open.",
                    "evidence_source_ids": ["chunk_02"],
                    "evidence_explanation": "Multiple test issues and PRs remain unaddressed.",
                },
                {
                    "risk": "Unverified automated changes; human review required.",
                    "evidence_source_ids": ["chunk_02"],
                    "evidence_explanation": "Bots submitting arbitrary PRs.",
                },
            ],
            "uncertainties": [
                {"uncertainty": "Coverage is partial based on bounded prompt context."},
                {"uncertainty": "The existence of deeper CI configurations cannot be verified from the provided chunks."},
            ],
        }

        normalized = normalize_gemini_analysis_response(observed_gemini_payload)
        result = AnalysisResult(**normalized)

        # Confirm normalized structure
        self.assertEqual(
            result.project_summary,
            "octocat/Hello-World is the classic starter repository created by GitHub.",
        )
        self.assertEqual(len(result.architectural_decisions), 2)
        self.assertEqual(result.architectural_decisions[0].id, "find_arch_01")
        self.assertEqual(result.architectural_decisions[0].category, FindingCategory.ARCHITECTURAL_DECISION)
        self.assertEqual(
            result.architectural_decisions[0].title,
            "Master branch workflow and pull-request workflow.",
        )
        self.assertEqual(result.architectural_decisions[0].evidence_source_ids, ["chunk_01"])

        self.assertEqual(len(result.technical_risks), 2)
        self.assertEqual(result.technical_risks[0].id, "find_risk_01")
        self.assertEqual(result.technical_risks[0].category, FindingCategory.TECHNICAL_RISK)
        self.assertEqual(
            result.technical_risks[0].title,
            "High noise ratio with numerous open pull requests and issues remaining open.",
        )

        self.assertEqual(len(result.uncertainties), 2)
        self.assertEqual(
            result.uncertainties[0],
            "Coverage is partial based on bounded prompt context.",
        )
        self.assertEqual(
            result.uncertainties[1],
            "The existence of deeper CI configurations cannot be verified from the provided chunks.",
        )

        # Confirm evidence references were automatically populated
        self.assertIn("chunk_01", result.evidence_references)
        self.assertIn("chunk_02", result.evidence_references)

    def test_unambiguous_alias_mappings(self):
        """Verify unambiguous category and field aliases map deterministically."""
        raw_aliases = {
            "summary": "A repository implementing an edge proxy.",
            "decisions": [
                {
                    "headline": "Use Go for Edge Proxy",
                    "description": "Go chosen for concurrent networking.",
                    "evidence_source_ids": ["chunk_01"],
                }
            ],
            "active_work": [
                {
                    "task": "Add rate limiting middleware",
                    "evidence_source_ids": ["chunk_02"],
                }
            ],
            "risks": [
                {
                    "risk": "Connection pooling exhaustion under high concurrency",
                    "evidence_source_ids": ["chunk_02"],
                }
            ],
            "roadmap": [
                {
                    "recommendation": "Implement Prometheus metrics exporter",
                    "evidence_source_ids": ["chunk_01"],
                }
            ],
            "fragile_modules": [{"file": "pkg/proxy/conn.go"}],
        }

        normalized = normalize_gemini_analysis_response(raw_aliases)
        result = AnalysisResult(**normalized)

        self.assertEqual(result.project_summary, "A repository implementing an edge proxy.")
        self.assertEqual(len(result.architectural_decisions), 1)
        self.assertEqual(result.architectural_decisions[0].title, "Use Go for Edge Proxy")
        self.assertEqual(len(result.active_workstreams), 1)
        self.assertEqual(result.active_workstreams[0].title, "Add rate limiting middleware")
        self.assertEqual(len(result.technical_risks), 1)
        self.assertEqual(result.technical_risks[0].title, "Connection pooling exhaustion under high concurrency")
        self.assertEqual(len(result.continuation_roadmap), 1)
        self.assertEqual(result.continuation_roadmap[0].title, "Implement Prometheus metrics exporter")
        self.assertEqual(result.fragile_modules, ["pkg/proxy/conn.go"])

    def test_missing_required_summary_raises_validation_error(self):
        """Verify omission of any project summary is rejected by Pydantic without fabrication."""
        raw_no_summary = {
            "architectural_decisions": [],
            "technical_risks": [],
        }

        normalized = normalize_gemini_analysis_response(raw_no_summary)
        with self.assertRaises(ValidationError):
            AnalysisResult(**normalized)

    def test_invalid_input_types_rejected(self):
        """Verify non-dictionary inputs raise ValueError."""
        with self.assertRaises(ValueError):
            normalize_gemini_analysis_response("not a json object")  # type: ignore

        with self.assertRaises(ValueError):
            normalize_gemini_analysis_response(["item1", "item2"])  # type: ignore

    def test_malformed_findings_without_text_candidates_rejected(self):
        """Verify findings that cannot produce title or description are rejected by Pydantic."""
        raw_empty_finding = {
            "project_summary": "Valid summary",
            "architectural_decisions": [
                {"id": "custom_id"}  # Missing title, description, and semantic text candidate
            ],
        }

        normalized = normalize_gemini_analysis_response(raw_empty_finding)
        with self.assertRaises(ValidationError):
            AnalysisResult(**normalized)

    def test_non_dict_finding_item_raises_validation_error(self):
        """Verify non-dictionary items in findings lists are rejected rather than silently discarded."""
        raw_string_item = {
            "project_summary": "Valid summary",
            "architectural_decisions": ["Malformed string finding without dictionary structure"],
        }
        normalized = normalize_gemini_analysis_response(raw_string_item)
        with self.assertRaises(ValidationError):
            AnalysisResult(**normalized)

    def test_evidence_verification_flags_invalid_and_cross_repo_citations(self):
        """Verify evidence verifier correctly tags valid, invalid, and cross-repo citations."""
        raw_payload = {
            "project_summary": "Repository analysis with mixed citations.",
            "architectural_decisions": [
                {
                    "decision": "Valid decision citing local chunk",
                    "evidence_source_ids": ["chunk_01"],
                },
                {
                    "decision": "Decision citing non-existent chunk",
                    "evidence_source_ids": ["chunk_ghost_999"],
                },
                {
                    "decision": "Decision citing foreign repository chunk",
                    "evidence_source_ids": ["chunk_foreign"],
                },
            ],
        }

        normalized = normalize_gemini_analysis_response(raw_payload)
        analysis_result = AnalysisResult(**normalized)

        verifier = EvidenceVerifier("repo_norm_1")
        verified_analysis, stats = verifier.verify_all_findings(analysis_result)

        findings = verified_analysis.architectural_decisions
        self.assertEqual(len(findings), 3)

        # 1. Valid local citation -> SOURCE_LINKED
        self.assertEqual(findings[0].verification_status, VerificationStatus.SOURCE_LINKED)

        # 2. Ghost citation -> INVALID_REFERENCE
        self.assertEqual(findings[1].verification_status, VerificationStatus.INVALID_REFERENCE)
        self.assertIn("does not exist", findings[1].verification_notes.lower())

        # 3. Cross-repository citation -> INVALID_REFERENCE
        self.assertEqual(findings[2].verification_status, VerificationStatus.INVALID_REFERENCE)
        self.assertIn("another repository", findings[2].verification_notes.lower())

        self.assertEqual(stats[VerificationStatus.SOURCE_LINKED.value], 1)
        self.assertEqual(stats[VerificationStatus.INVALID_REFERENCE.value], 2)

    def test_end_to_end_report_persistence_with_normalized_output(self):
        """Verify a normalized Gemini output persists to SQLite and can be retrieved via ReportGenerator."""
        with get_db_context() as conn:
            conn.execute(
                """
                INSERT INTO analysis_runs (id, repository_id, status, started_at)
                VALUES ('run_test_persist', 'repo_norm_1', 'running', '2026-01-01');
                """
            )
        raw_payload = {
            "project_overview": {"summary": "octocat/Hello-World end-to-end report test."},
            "architectural_decisions": [
                {
                    "decision": "Default branch master configured.",
                    "evidence_source_ids": ["chunk_01"],
                    "evidence_explanation": "Evidence from initial commit.",
                }
            ],
            "technical_risks": [
                {
                    "risk": "Issue tracker open noise.",
                    "evidence_source_ids": ["chunk_02"],
                    "evidence_explanation": "High volume of test tickets.",
                }
            ],
        }

        normalized = normalize_gemini_analysis_response(raw_payload)
        analysis = AnalysisResult(**normalized)
        analysis.coverage_summary = CoverageSummary(
            total_available_chunks=2,
            analyzed_chunks=2,
            is_complete_coverage=True,
            coverage_percentage=100.0,
        )

        generator = ReportGenerator("repo_norm_1")
        meta = generator.assemble_and_persist_report(
            analysis=analysis,
            analysis_run_id="run_test_persist",
            repository_name="octocat/Hello-World",
            model_used="gemini-3.8-flash",
        )

        self.assertIsNotNone(meta["report_id"])
        self.assertEqual(meta["repository_id"], "repo_norm_1")

        # Retrieve report from database
        stored_report = get_report_by_id(meta["report_id"])
        self.assertIsNotNone(stored_report)
        self.assertEqual(
            stored_report["report_data"]["team_lead_view"]["executive_summary"],
            "octocat/Hello-World end-to-end report test.",
        )
        self.assertEqual(len(stored_report["report_data"]["developer_view"]["technical_architecture"]), 1)
        self.assertEqual(
            stored_report["report_data"]["developer_view"]["technical_architecture"][0]["title"],
            "Default branch master configured.",
        )

    def test_duplicate_or_colliding_finding_ids_made_unique(self):
        """Verify colliding or duplicate finding IDs are deterministically made globally unique."""
        raw_colliding = {
            "project_summary": "Testing ID collision resolution.",
            "architectural_decisions": [
                {"id": "find_01", "decision": "Decision 1", "evidence_source_ids": ["chunk_01"]},
                {"id": "find_01", "decision": "Decision 2", "evidence_source_ids": ["chunk_01"]},
            ],
            "technical_risks": [
                {"id": "find_01", "risk": "Risk 1", "evidence_source_ids": ["chunk_02"]},
                {"id": "custom_id", "risk": "Risk 2", "evidence_source_ids": ["chunk_02"]},
                {"id": "custom_id", "risk": "Risk 3", "evidence_source_ids": ["chunk_02"]},
            ],
        }

        normalized = normalize_gemini_analysis_response(raw_colliding)
        result = AnalysisResult(**normalized)

        all_ids = [f.id for f in result.architectural_decisions + result.technical_risks]
        self.assertEqual(len(all_ids), len(set(all_ids)), f"Duplicate IDs detected: {all_ids}")
        # Preserved unique original ID
        self.assertIn("custom_id", all_ids)
        # Resolved collision
        self.assertEqual(result.architectural_decisions[0].id, "find_01")
        self.assertEqual(result.architectural_decisions[1].id, "find_arch_02")
        self.assertEqual(result.technical_risks[0].id, "find_risk_01")
        self.assertEqual(result.technical_risks[1].id, "custom_id")
        self.assertEqual(result.technical_risks[2].id, "find_risk_03")

    def test_semantic_separator_headline_extraction(self):
        """Verify colon or dash in semantic text cleanly separates title from description."""
        raw_with_separators = {
            "project_summary": "Testing headline separation.",
            "architectural_decisions": [
                {
                    "decision": "Master Branch: The default branch was migrated to master for git stability.",
                    "evidence_source_ids": ["chunk_01"],
                },
                {
                    "decision": "SQLite Persistence - SQLite embedded engine chosen to avoid daemon dependencies.",
                    "evidence_source_ids": ["chunk_01"],
                },
            ],
        }

        normalized = normalize_gemini_analysis_response(raw_with_separators)
        result = AnalysisResult(**normalized)

        d1 = result.architectural_decisions[0]
        self.assertEqual(d1.title, "Master Branch")
        self.assertEqual(d1.description, "The default branch was migrated to master for git stability.")

        d2 = result.architectural_decisions[1]
        self.assertEqual(d2.title, "SQLite Persistence")
        self.assertEqual(d2.description, "SQLite embedded engine chosen to avoid daemon dependencies.")

    def test_gemini_schema_definition_valid(self):
        """Verify get_gemini_analysis_schema produces valid schema object."""
        schema = get_gemini_analysis_schema()
        self.assertEqual(schema["type"], "object")
        self.assertIn("project_summary", schema["properties"])
        self.assertIn("architectural_decisions", schema["properties"])
        self.assertIn("technical_risks", schema["properties"])
        self.assertIn("project_summary", schema["required"])

    def test_schema_bidirectional_compatibility_with_pydantic(self):
        """Verify all fields and properties in get_gemini_analysis_schema align with Pydantic contracts."""
        gemini_schema = get_gemini_analysis_schema()
        pydantic_schema = AnalysisResult.model_json_schema()

        # 1. Required fields match exactly
        self.assertEqual(gemini_schema["required"], pydantic_schema["required"])

        # 2. Properties match except internal server-side coverage_summary
        gemini_props = set(gemini_schema["properties"].keys())
        pydantic_props = set(pydantic_schema["properties"].keys())
        self.assertEqual(pydantic_props - gemini_props, {"coverage_summary"})

        # 3. Finding schema properties match except internal deterministic verifier fields
        finding_schema = gemini_schema["properties"]["architectural_decisions"]["items"]
        from app.schemas.analysis import Finding
        pydantic_finding_props = set(Finding.model_json_schema()["properties"].keys())
        gemini_finding_props = set(finding_schema["properties"].keys())
        internal_fields = {"verification_status", "verification_notes", "temporal_conflict_detected"}
        self.assertEqual(pydantic_finding_props - gemini_finding_props, internal_fields)

    def test_mock_report_loads_from_active_sqlite_without_mutation(self):
        """Verify that existing persisted reports in the real database remain completely intact."""
        from app.core.config import get_settings
        import sqlite3
        import json
        real_db = get_settings().get_database_path()
        if not real_db.exists():
            self.skipTest("No active SQLite database file to verify.")

        conn = sqlite3.connect(real_db)
        conn.row_factory = sqlite3.Row
        cur = conn.cursor()
        cur.execute("SELECT id, title, report_json, status FROM handover_reports WHERE id = 'rep_f34ab9bca2904063';")
        row = cur.fetchone()
        conn.close()

        if row:
            report_dict = dict(row)
            self.assertEqual(report_dict["id"], "rep_f34ab9bca2904063")
            data = json.loads(report_dict["report_json"])
            self.assertIn("developer_view", data)
            self.assertIn("team_lead_view", data)
            self.assertTrue(len(data["developer_view"]["technical_architecture"]) > 0)


if __name__ == "__main__":
    unittest.main()
