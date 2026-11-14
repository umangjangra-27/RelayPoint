"""Handover Report Generation, Role-Tailored Views, and Persistence Service.

Assembles developer and team-lead views, links verified evidence citations,
and persists versioned handover reports into SQLite.
"""

from datetime import datetime, timezone
import json
import logging
from typing import Any, Dict, List, Optional
import uuid

from app.core.database import get_db_context
from app.schemas.analysis import (
    AnalysisResult,
    DeveloperView,
    Finding,
    HandoverReportPayload,
    TeamLeadView,
    VerificationStatus,
)
from app.services.verifier import EvidenceVerifier

logger = logging.getLogger("relaypoint.report_generator")


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _generate_id(prefix: str) -> str:
    """Generate unique prefixed identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


class ReportGenerator:
    """Generates, parses, and persists role-specific handover reports."""

    def __init__(self, repo_id: str):
        self.repo_id = repo_id
        self.verifier = EvidenceVerifier(repo_id)

    def assemble_and_persist_report(
        self,
        analysis: AnalysisResult,
        analysis_run_id: str,
        repository_name: str,
        model_used: str,
    ) -> Dict[str, Any]:
        """Verify findings, construct role-based views, and store report into SQLite."""
        # 1. Deterministic Evidence Verification
        verified_analysis, verification_stats = self.verifier.verify_all_findings(analysis)

        # 2. Extract Evidence Appendix for Developer View
        appendix = self._build_evidence_appendix(verified_analysis)

        # 3. Assemble Developer View
        developer_view = DeveloperView(
            technical_architecture=verified_analysis.architectural_decisions,
            active_code_work=verified_analysis.active_workstreams,
            unfinished_implementations=verified_analysis.unfinished_work,
            blockers_and_failing_areas=verified_analysis.blockers,
            fragile_files=verified_analysis.fragile_modules,
            immediate_tasks=verified_analysis.continuation_roadmap,
            evidence_appendix=appendix,
        )

        # 4. Assess Project Health for Team Lead View
        health_status = self._compute_project_health(verified_analysis)

        # Filter critical blockers and high risks for lead view
        critical_blockers = [b for b in verified_analysis.blockers if b.priority.value == "high"]
        critical_risks = [r for r in verified_analysis.technical_risks if r.priority.value in ("high", "medium")]
        lead_blockers_and_risks = critical_blockers + critical_risks

        team_lead_view = TeamLeadView(
            executive_summary=verified_analysis.project_summary,
            project_health_status=health_status,
            major_milestones_and_workstreams=verified_analysis.active_workstreams,
            critical_blockers_and_risks=lead_blockers_and_risks,
            strategic_priorities=verified_analysis.continuation_roadmap,
            coverage_overview=verified_analysis.coverage_summary,
            uncertainties_and_open_questions=verified_analysis.uncertainties,
        )

        # 5. Compile Master Handover Payload
        now = _now_iso()
        report_id = _generate_id("rep")
        report_title = f"Knowledge Handover: {repository_name} ({now[:10]})"

        # Combine all findings
        all_findings = (
            verified_analysis.architectural_decisions
            + verified_analysis.active_workstreams
            + verified_analysis.unfinished_work
            + verified_analysis.blockers
            + verified_analysis.technical_risks
            + verified_analysis.continuation_roadmap
        )

        report_payload = HandoverReportPayload(
            title=report_title,
            repository_id=self.repo_id,
            repository_name=repository_name,
            analysis_run_id=analysis_run_id,
            generated_at=now,
            model_used=model_used,
            developer_view=developer_view,
            team_lead_view=team_lead_view,
            raw_findings=all_findings,
            coverage=verified_analysis.coverage_summary,
            verification_stats=verification_stats,
        )

        # 6. Persist to SQLite handover_reports table
        report_json_str = report_payload.model_dump_json()

        with get_db_context() as conn:
            conn.execute(
                """
                INSERT INTO handover_reports (
                    id, repository_id, analysis_run_id, title, report_json, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 'draft', ?, ?);
                """,
                (
                    report_id,
                    self.repo_id,
                    analysis_run_id,
                    report_title,
                    report_json_str,
                    now,
                    now,
                ),
            )

            # 7. Persist atomic evidence links into evidence_references table
            for finding in all_findings:
                for sid in finding.evidence_source_ids:
                    chunk = self.verifier._source_cache.get(sid)
                    if chunk:
                        ev_id = _generate_id("ev")
                        conn.execute(
                            """
                            INSERT INTO evidence_references (
                                id, analysis_run_id, source_chunk_id, reference_type,
                                reference_identifier, source_url, created_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?);
                            """,
                            (
                                ev_id,
                                analysis_run_id,
                                sid,
                                finding.category.value,
                                finding.id,
                                chunk.get("source_url"),
                                now,
                            ),
                        )

        return {
            "report_id": report_id,
            "title": report_title,
            "repository_id": self.repo_id,
            "analysis_run_id": analysis_run_id,
            "verification_stats": verification_stats,
            "created_at": now,
        }

    def _build_evidence_appendix(self, analysis: AnalysisResult) -> List[Dict[str, Any]]:
        """Collect and format all unique cited source chunks for developer inspection."""
        cited_ids = set()
        finding_lists = [
            analysis.architectural_decisions,
            analysis.active_workstreams,
            analysis.unfinished_work,
            analysis.blockers,
            analysis.technical_risks,
            analysis.continuation_roadmap,
        ]
        for collection in finding_lists:
            for f in collection:
                cited_ids.update(f.evidence_source_ids)

        appendix = []
        for sid in sorted(cited_ids):
            chunk = self.verifier._source_cache.get(sid)
            if chunk:
                appendix.append({
                    "source_id": chunk["id"],
                    "source_type": chunk.get("source_type"),
                    "external_id": chunk.get("source_external_id"),
                    "commit_hash": chunk.get("commit_hash"),
                    "source_url": chunk.get("source_url"),
                    "content_preview": chunk.get("content", "")[:300],
                    "metadata": chunk.get("metadata", {}),
                    "verified": True,
                })
            else:
                appendix.append({
                    "source_id": sid,
                    "source_type": "unknown",
                    "verified": False,
                    "error": "Source ID was cited by AI model but is not present in SQLite database.",
                })
        return appendix

    def _compute_project_health(self, analysis: AnalysisResult) -> str:
        """Derive objective health status from verified blocker and risk counts."""
        blocker_count = len(analysis.blockers)
        high_risk_count = len([r for r in analysis.technical_risks if r.priority.value == "high"])

        if blocker_count >= 3 or high_risk_count >= 3:
            return "Attention Required - Multiple critical blockers and high risks detected"
        elif blocker_count > 0 or high_risk_count > 0:
            return "Active Development with Blockers - Outstanding technical items require resolution"
        return "Healthy Momentum - Active workstreams progressing without critical blockers"


def get_report_by_id(report_id: str) -> Optional[Dict[str, Any]]:
    """Retrieve and deserialize a saved handover report from SQLite."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM handover_reports WHERE id = ?;", (report_id,))
        row = cursor.fetchone()
        if not row:
            return None

        report_dict = dict(row)
        try:
            report_dict["report_data"] = json.loads(report_dict["report_json"])
        except Exception:
            report_dict["report_data"] = {}
        return report_dict


def list_reports_for_repository(repo_id: str) -> List[Dict[str, Any]]:
    """Retrieve summary metadata for all reports associated with a repository."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT id, repository_id, analysis_run_id, title, status, created_at, updated_at, report_json
            FROM handover_reports
            WHERE repository_id = ?
            ORDER BY created_at DESC;
            """,
            (repo_id,),
        )
        rows = cursor.fetchall()

    summaries = []
    for r in rows:
        item = dict(r)
        try:
            data = json.loads(item.pop("report_json", "{}"))
            item["model_used"] = data.get("model_used")
            item["verification_stats"] = data.get("verification_stats")
        except Exception:
            item["model_used"] = None
            item["verification_stats"] = None
        summaries.append(item)
    return summaries


def reverify_report(report_id: str) -> Dict[str, Any]:
    """Re-run deterministic verification against current stored sources for a report."""
    report = get_report_by_id(report_id)
    if not report:
        raise ValueError(f"Report '{report_id}' not found.")

    payload_dict = report["report_data"]
    repo_id = report["repository_id"]
    verifier = EvidenceVerifier(repo_id)

    raw_findings = [Finding(**f) for f in payload_dict.get("raw_findings", [])]

    # Re-verify all findings
    stats = {
        VerificationStatus.SOURCE_LINKED.value: 0,
        VerificationStatus.INVALID_REFERENCE.value: 0,
        VerificationStatus.INSUFFICIENT_EVIDENCE.value: 0,
        VerificationStatus.NEEDS_HUMAN_REVIEW.value: 0,
    }

    for f in raw_findings:
        verifier.verify_finding(f)
        status_key = f.verification_status.value
        stats[status_key] = stats.get(status_key, 0) + 1

    # Update payload
    payload_dict["raw_findings"] = [f.model_dump() for f in raw_findings]
    payload_dict["verification_stats"] = stats
    now = _now_iso()

    with get_db_context() as conn:
        conn.execute(
            """
            UPDATE handover_reports
            SET report_json = ?, updated_at = ?
            WHERE id = ?;
            """,
            (json.dumps(payload_dict), now, report_id),
        )

    return {
        "report_id": report_id,
        "status": "reverified",
        "verification_stats": stats,
        "updated_at": now,
    }
