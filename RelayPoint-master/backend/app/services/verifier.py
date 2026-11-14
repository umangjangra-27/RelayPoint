"""Deterministic Evidence Verification and Temporal Conflict Engine.

Audits every AI-generated claim against ground-truth SQLite source chunks:
- Validates source chunk existence and repository ownership
- Validates cryptographic SHA-256 content hashes
- Identifies missing or fabricated evidence citations
- Detects temporal conflicts (e.g. closed PRs or resolved issues claimed as active)
- Assigns deterministic verification status: SOURCE_LINKED, INVALID_REFERENCE,
  INSUFFICIENT_EVIDENCE, or NEEDS_HUMAN_REVIEW
"""

import hashlib
import json
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

from app.core.database import get_db_context
from app.schemas.analysis import (
    AnalysisResult,
    Finding,
    VerificationStatus,
)

logger = logging.getLogger("relaypoint.verifier")


class EvidenceVerifier:
    """Verifies citation integrity and temporal consistency of synthesized findings."""

    def __init__(self, repo_id: str):
        self.repo_id = repo_id
        self._source_cache: Dict[str, Dict[str, Any]] = {}
        self._load_repository_sources()

    def _load_repository_sources(self) -> None:
        """Cache all stored sources for the repository to perform rapid in-memory verification."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                SELECT id, repository_id, source_type, source_external_id,
                       commit_hash, content, content_hash, source_url,
                       metadata_json, created_at
                FROM source_chunks
                WHERE repository_id = ?;
                """,
                (self.repo_id,),
            )
            rows = cursor.fetchall()

        for r in rows:
            item = dict(r)
            try:
                item["metadata"] = json.loads(item.get("metadata_json", "{}"))
            except Exception:
                item["metadata"] = {}
            self._source_cache[item["id"]] = item

    def verify_finding(self, finding: Finding) -> Finding:
        """Perform comprehensive deterministic audit on a single finding."""
        cited_ids = finding.evidence_source_ids

        # 1. Check for absence of evidence
        if not cited_ids:
            finding.verification_status = VerificationStatus.INSUFFICIENT_EVIDENCE
            finding.verification_notes = "No supporting evidence source IDs were cited."
            return finding

        valid_sources: List[Dict[str, Any]] = []
        invalid_reasons: List[str] = []

        for sid in cited_ids:
            # Check source existence
            if sid not in self._source_cache:
                # Check if it exists in another repository
                if self._check_exists_in_other_repo(sid):
                    invalid_reasons.append(f"Source ID '{sid}' belongs to another repository.")
                else:
                    invalid_reasons.append(f"Source ID '{sid}' does not exist in SQLite database.")
                continue

            chunk = self._source_cache[sid]

            # Verify repository ownership
            if chunk["repository_id"] != self.repo_id:
                invalid_reasons.append(f"Source ID '{sid}' cross-references unauthorized repository.")
                continue

            # Verify cryptographic SHA-256 content hash integrity
            expected_hash = hashlib.sha256(chunk["content"].encode("utf-8")).hexdigest()
            if chunk["content_hash"] != expected_hash:
                invalid_reasons.append(f"Cryptographic content hash mismatch for source ID '{sid}'.")
                continue

            valid_sources.append(chunk)

        # If any cited reference is invalid, mark INVALID_REFERENCE
        if invalid_reasons:
            finding.verification_status = VerificationStatus.INVALID_REFERENCE
            finding.verification_notes = "; ".join(invalid_reasons)
            return finding

        # 2. Temporal Conflict and Consistency Check
        conflict, conflict_reason = self._check_temporal_conflict(finding, valid_sources)
        if conflict:
            finding.temporal_conflict_detected = True
            finding.verification_status = VerificationStatus.NEEDS_HUMAN_REVIEW
            finding.verification_notes = f"Temporal conflict detected: {conflict_reason}"
            return finding

        # 3. Passed all integrity checks: Successfully SOURCE_LINKED
        finding.verification_status = VerificationStatus.SOURCE_LINKED
        notes_parts = [f"Traceable to {len(valid_sources)} verified source chunk(s)"]
        for s in valid_sources:
            ext_id = s.get("source_external_id") or s.get("commit_hash")
            if ext_id:
                notes_parts.append(f"{s['source_type']} #{ext_id}")
        finding.verification_notes = ", ".join(notes_parts)
        return finding

    def _check_temporal_conflict(
        self,
        finding: Finding,
        sources: List[Dict[str, Any]],
    ) -> Tuple[bool, Optional[str]]:
        """Detect contradictions between claim category and underlying source state."""
        category = finding.category.value
        title_lower = finding.title.lower()
        desc_lower = finding.description.lower()

        for s in sources:
            stype = s.get("source_type")
            meta = s.get("metadata", {})
            state = meta.get("state", "").lower()

            # Conflict 1: Claiming an issue or PR is active/unfinished/blocker when source says it is closed/merged
            if category in ("active_work", "unfinished_work", "blocker"):
                if stype in ("issue", "pull_request") and state in ("closed", "merged"):
                    return (
                        True,
                        f"Claimed as {category}, but source {stype} #{s.get('source_external_id')} is marked '{state}'.",
                    )
                if meta.get("merged_at"):
                    return (
                        True,
                        f"Claimed as ongoing, but pull request #{s.get('source_external_id')} was merged at {meta.get('merged_at')}.",
                    )

            # Conflict 2: Claiming an issue is resolved or finished when the only cited source is still open
            if category in ("architectural_decision",) and ("resolved" in title_lower or "fixed" in title_lower):
                if stype == "issue" and state == "open":
                    return (
                        True,
                        f"Claimed as completed decision, but referenced issue #{s.get('source_external_id')} remains open.",
                    )

        return False, None

    def _check_exists_in_other_repo(self, chunk_id: str) -> bool:
        """Check if chunk exists in any other repository to catch cross-repo hallucination."""
        with get_db_context() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT repository_id FROM source_chunks WHERE id = ?;", (chunk_id,))
            row = cursor.fetchone()
            return row is not None

    def verify_all_findings(self, analysis: AnalysisResult) -> Tuple[AnalysisResult, Dict[str, int]]:
        """Run verification on all finding collections in the AnalysisResult.
        
        Returns:
            (updated AnalysisResult, verification statistics dictionary)
        """
        stats: Dict[str, int] = {
            VerificationStatus.SOURCE_LINKED.value: 0,
            VerificationStatus.INVALID_REFERENCE.value: 0,
            VerificationStatus.INSUFFICIENT_EVIDENCE.value: 0,
            VerificationStatus.NEEDS_HUMAN_REVIEW.value: 0,
        }

        finding_lists = [
            analysis.architectural_decisions,
            analysis.active_workstreams,
            analysis.unfinished_work,
            analysis.blockers,
            analysis.technical_risks,
            analysis.continuation_roadmap,
        ]

        for collection in finding_lists:
            for finding in collection:
                self.verify_finding(finding)
                status_key = finding.verification_status.value
                stats[status_key] = stats.get(status_key, 0) + 1

        return analysis, stats
