"""AI Analysis and Handover Report Generation API Endpoints."""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, HTTPException, status

from app.core.config import get_settings
from app.core.database import get_db_context
from app.integrations.gemini import (
    GeminiAuthError,
    GeminiError,
    GeminiModelNotFoundError,
    GeminiQuotaError,
)
from app.schemas.analysis import (
    ReportDetailResponse,
    ReportSummaryResponse,
)
from app.services.analyzer import RepositoryAnalyzer
from app.services.report_generator import (
    ReportGenerator,
    get_report_by_id,
    list_reports_for_repository,
    reverify_report,
)

logger = logging.getLogger("relaypoint.api.analysis")

router = APIRouter(tags=["Analysis & Reports"])


def _generate_id(prefix: str) -> str:
    """Generate unique prefixed identifier."""
    return f"{prefix}_{uuid.uuid4().hex[:16]}"


def _now_iso() -> str:
    """Return current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


@router.post(
    "/repositories/{repository_id}/analyze",
    status_code=status.HTTP_201_CREATED,
    summary="Trigger AI Knowledge Synthesis and Handover Report Generation",
    description="Prepares bounded context from sanitized chunks, invokes Gemini for structured synthesis, verifies citations, and generates role-based handover reports.",
)
def analyze_repository(repository_id: str) -> Dict[str, Any]:
    """Execute end-to-end AI synthesis and evidence-linked report generation."""
    settings = get_settings()

    # 1. Verify Repository Existence
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id, name, full_name FROM repositories WHERE id = ?;", (repository_id,))
        repo = cursor.fetchone()
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository '{repository_id}' not found.",
            )
        repo_name = repo["full_name"] or repo["name"]

        # 2. Verify Ingested Sources Exist
        cursor.execute("SELECT count(*) FROM source_chunks WHERE repository_id = ?;", (repository_id,))
        chunk_count = cursor.fetchone()[0]
        if chunk_count == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Repository has no ingested source chunks. Please run ingestion before triggering analysis.",
            )

    # 3. Check Gemini API Configuration
    analyzer = RepositoryAnalyzer()
    if not analyzer.gemini_client.is_configured:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="GEMINI_API_KEY is not configured. Please configure your API key in environment or .env file.",
        )

    # 4. Create Analysis Run
    run_id = _generate_id("run")
    start_time = _now_iso()
    with get_db_context() as conn:
        conn.execute(
            """
            INSERT INTO analysis_runs (id, repository_id, status, started_at)
            VALUES (?, ?, 'running', ?);
            """,
            (run_id, repository_id, start_time),
        )

    try:
        # 5. Execute Structured Synthesis
        analysis_result, selected_chunks = analyzer.analyze_repository(repository_id)

        # 6. Verify Evidence & Persist Report
        generator = ReportGenerator(repository_id)
        report_meta = generator.assemble_and_persist_report(
            analysis=analysis_result,
            analysis_run_id=run_id,
            repository_name=repo_name,
            model_used=settings.GEMINI_MODEL,
        )

        # 7. Update Analysis Run Status
        completion_time = _now_iso()
        with get_db_context() as conn:
            conn.execute(
                """
                UPDATE analysis_runs
                SET status = 'completed', completed_at = ?
                WHERE id = ?;
                """,
                (completion_time, run_id),
            )

        return report_meta

    except GeminiAuthError as auth_err:
        _mark_run_failed(run_id, str(auth_err))
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(auth_err))
    except GeminiQuotaError as quota_err:
        _mark_run_failed(run_id, str(quota_err))
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=str(quota_err))
    except GeminiModelNotFoundError as model_err:
        _mark_run_failed(run_id, str(model_err))
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(model_err))
    except Exception as exc:
        logger.error("Analysis failed for repository %s: %s", repository_id, exc)
        _mark_run_failed(run_id, "Synthesis failed during AI processing or evidence verification.")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="AI synthesis failed. Please ensure the model is accessible and try again.",
        )


def _mark_run_failed(run_id: str, error_message: str) -> None:
    """Helper to update analysis run record to failed status safely."""
    try:
        with get_db_context() as conn:
            conn.execute(
                """
                UPDATE analysis_runs
                SET status = 'failed', completed_at = ?, error_message = ?
                WHERE id = ?;
                """,
                (_now_iso(), error_message, run_id),
            )
    except Exception as exc:
        logger.error("Could not update analysis run failure status: %s", exc)


@router.get(
    "/repositories/{repository_id}/reports",
    response_model=List[ReportSummaryResponse],
    summary="List Handover Reports for a Repository",
    description="Retrieve summaries of all synthesized handover reports for the specified repository.",
)
def get_repository_reports(repository_id: str) -> List[ReportSummaryResponse]:
    """List handover report summaries."""
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM repositories WHERE id = ?;", (repository_id,))
        if not cursor.fetchone():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Repository '{repository_id}' not found.",
            )

    reports = list_reports_for_repository(repository_id)
    return [ReportSummaryResponse(**r) for r in reports]


@router.get(
    "/reports/{report_id}",
    response_model=ReportDetailResponse,
    summary="Retrieve Full Handover Report",
    description="Returns the complete handover report document including developer view, team lead view, and verification metadata.",
)
def get_report(report_id: str) -> ReportDetailResponse:
    """Retrieve complete report by ID."""
    report = get_report_by_id(report_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Handover report '{report_id}' not found.",
        )
    return ReportDetailResponse(**report)


@router.post(
    "/reports/{report_id}/verify",
    summary="Re-run Deterministic Evidence Verification",
    description="Audits and recalculates citation integrity, SHA-256 hashes, and temporal consistency against current stored sources.",
)
def reverify_existing_report(report_id: str) -> Dict[str, Any]:
    """Re-verify existing report findings."""
    try:
        return reverify_report(report_id)
    except ValueError as val_err:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(val_err))
    except Exception as exc:
        logger.error("Reverification failed for report %s: %s", report_id, exc)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to reverify report against stored evidence.",
        )
