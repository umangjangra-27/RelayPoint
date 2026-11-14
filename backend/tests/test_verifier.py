"""Unit tests for deterministic evidence verification and conflict detection."""

import hashlib
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
    VerificationStatus,
)
from app.services.verifier import EvidenceVerifier


class TestEvidenceVerifier(unittest.TestCase):
    """Test suite for deterministic citation verifier."""

    def setUp(self):
        """Create temporary test database and seed test repository with chunks."""
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test_verifier.db"

        self.db_patcher = patch("app.core.database.get_db_path", return_value=self.db_path)
        self.db_patcher.start()
        init_db(self.db_path)

        # Content and SHA-256 hashes
        self.c1_content = "feat: add user authentication with JWT"
        self.c1_hash = hashlib.sha256(self.c1_content.encode("utf-8")).hexdigest()

        self.c2_content = "fix: resolve memory leak in worker pool"
        self.c2_hash = hashlib.sha256(self.c2_content.encode("utf-8")).hexdigest()

        self.c_pr_content = "Merged PR #50"
        self.c_pr_hash = hashlib.sha256(self.c_pr_content.encode("utf-8")).hexdigest()

        with get_db_context() as conn:
            # Main repo
            conn.execute(
                """
                INSERT INTO repositories (id, provider, name, full_name, default_branch, repository_url, created_at, updated_at)
                VALUES ('repo_A', 'github', 'repo-a', 'owner/repo-a', 'main', 'https://github.com/owner/repo-a', '2026-01-01', '2026-01-01');
                """
            )
            # Other repo
            conn.execute(
                """
                INSERT INTO repositories (id, provider, name, full_name, default_branch, repository_url, created_at, updated_at)
                VALUES ('repo_B', 'github', 'repo-b', 'owner/repo-b', 'main', 'https://github.com/owner/repo-b', '2026-01-01', '2026-01-01');
                """
            )

            # Valid commit chunk for repo_A
            conn.execute(
                """
                INSERT INTO source_chunks (id, repository_id, source_type, source_external_id, commit_hash, content, content_hash, created_at)
                VALUES ('chunk_1', 'repo_A', 'commit', 'sha111', 'sha111', ?, ?, '2026-01-01');
                """,
                (self.c1_content, self.c1_hash),
            )

            # Closed PR chunk for repo_A (for conflict testing)
            conn.execute(
                """
                INSERT INTO source_chunks (id, repository_id, source_type, source_external_id, content, content_hash, metadata_json, created_at)
                VALUES ('chunk_closed_pr', 'repo_A', 'pull_request', '50', ?, ?, '{"state": "closed", "merged_at": "2026-01-02T00:00:00Z"}', '2026-01-02');
                """,
                (self.c_pr_content, self.c_pr_hash),
            )

            # Chunk belonging to repo_B
            conn.execute(
                """
                INSERT INTO source_chunks (id, repository_id, source_type, source_external_id, content, content_hash, created_at)
                VALUES ('chunk_foreign', 'repo_B', 'commit', 'sha222', ?, ?, '2026-01-01');
                """,
                (self.c2_content, self.c2_hash),
            )

        self.verifier = EvidenceVerifier(repo_id="repo_A")

    def tearDown(self):
        """Clean up test resources."""
        self.db_patcher.stop()
        self.temp_dir.cleanup()

    def test_valid_citation_marked_source_linked(self):
        """Verify properly cited, existing, hash-verified chunks are marked SOURCE_LINKED."""
        finding = Finding(
            id="f1",
            category=FindingCategory.ARCHITECTURAL_DECISION,
            title="JWT Authentication",
            description="System uses JWT for tokens.",
            evidence_source_ids=["chunk_1"],
        )
        self.verifier.verify_finding(finding)

        self.assertEqual(finding.verification_status, VerificationStatus.SOURCE_LINKED)
        self.assertIn("verified", (finding.verification_notes or "").lower())

    def test_missing_evidence_marked_insufficient(self):
        """Verify findings with empty citations are marked INSUFFICIENT_EVIDENCE."""
        finding = Finding(
            id="f2",
            category=FindingCategory.BLOCKER,
            title="Unsubstantiated Blocker",
            description="A blocker with no citations.",
            evidence_source_ids=[],
        )
        self.verifier.verify_finding(finding)

        self.assertEqual(finding.verification_status, VerificationStatus.INSUFFICIENT_EVIDENCE)

    def test_non_existent_source_id_marked_invalid(self):
        """Verify citing a hallucinated source ID is marked INVALID_REFERENCE."""
        finding = Finding(
            id="f3",
            category=FindingCategory.ACTIVE_WORK,
            title="Hallucinated Feature",
            description="References a fake ID.",
            evidence_source_ids=["chunk_does_not_exist_999"],
        )
        self.verifier.verify_finding(finding)

        self.assertEqual(finding.verification_status, VerificationStatus.INVALID_REFERENCE)
        self.assertIn("does not exist", finding.verification_notes or "")

    def test_cross_repository_source_marked_invalid(self):
        """Verify citing a chunk from an unauthorized/different repository is marked INVALID_REFERENCE."""
        finding = Finding(
            id="f4",
            category=FindingCategory.ARCHITECTURAL_DECISION,
            title="Cross-Repo Hallucination",
            description="Cites chunk from repo_B.",
            evidence_source_ids=["chunk_foreign"],
        )
        self.verifier.verify_finding(finding)

        self.assertEqual(finding.verification_status, VerificationStatus.INVALID_REFERENCE)
        self.assertIn("another repository", finding.verification_notes or "")

    def test_temporal_conflict_detection(self):
        """Verify claiming a closed/merged PR as active work triggers NEEDS_HUMAN_REVIEW."""
        finding = Finding(
            id="f5",
            category=FindingCategory.ACTIVE_WORK,
            title="Ongoing PR Work",
            description="Claimed as active workstream.",
            evidence_source_ids=["chunk_closed_pr"],
        )
        self.verifier.verify_finding(finding)

        self.assertEqual(finding.verification_status, VerificationStatus.NEEDS_HUMAN_REVIEW)
        self.assertTrue(finding.temporal_conflict_detected)
        self.assertIn("Temporal conflict", finding.verification_notes or "")


if __name__ == "__main__":
    unittest.main()
