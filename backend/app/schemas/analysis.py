"""Pydantic v2 schemas for AI synthesis, evidence verification, and handover reports."""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class FindingCategory(str, Enum):
    """Categories of synthesized findings."""
    ARCHITECTURAL_DECISION = "architectural_decision"
    ACTIVE_WORK = "active_work"
    UNFINISHED_WORK = "unfinished_work"
    BLOCKER = "blocker"
    TECHNICAL_RISK = "technical_risk"
    CONTINUATION_RECOMMENDATION = "continuation_recommendation"


class PriorityLevel(str, Enum):
    """Priority classifications."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ConfidenceLevel(str, Enum):
    """Model confidence levels based on cited evidence."""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class VerificationStatus(str, Enum):
    """Deterministic verification status of a finding."""
    SOURCE_LINKED = "SOURCE_LINKED"
    INVALID_REFERENCE = "INVALID_REFERENCE"
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"
    NEEDS_HUMAN_REVIEW = "NEEDS_HUMAN_REVIEW"


class Finding(BaseModel):
    """An individual evidence-grounded finding."""
    id: str = Field(..., description="Unique identifier for the finding (e.g. find_01)")
    category: FindingCategory = Field(..., description="Classification category")
    title: str = Field(..., description="Concise headline of the finding")
    description: str = Field(..., description="Detailed description based on repository activity")
    priority: PriorityLevel = Field(default=PriorityLevel.MEDIUM, description="Action priority")
    confidence: ConfidenceLevel = Field(default=ConfidenceLevel.MEDIUM, description="Grounding confidence")
    evidence_source_ids: List[str] = Field(
        default_factory=list,
        description="List of source_chunk IDs from SQLite that back this finding",
    )
    evidence_explanation: str = Field(
        default="",
        description="Explanation of how the cited sources support the claim",
    )
    verification_status: VerificationStatus = Field(
        default=VerificationStatus.INSUFFICIENT_EVIDENCE,
        description="Status computed by deterministic verifier",
    )
    verification_notes: Optional[str] = Field(
        default=None,
        description="Verifier audit trail (e.g. validated commit hash, missing ID, etc.)",
    )
    temporal_conflict_detected: bool = Field(
        default=False,
        description="True if contradictory later activity was detected",
    )


class CoverageSummary(BaseModel):
    """Metric summary of analyzed repository coverage."""
    total_available_chunks: int = Field(..., description="Total sanitized chunks available in SQLite")
    analyzed_chunks: int = Field(..., description="Count of chunks included in prompt budget")
    is_complete_coverage: bool = Field(..., description="True if 100% of available chunks were analyzed")
    coverage_percentage: float = Field(..., description="Percentage of history analyzed")
    oldest_chunk_date: Optional[str] = None
    newest_chunk_date: Optional[str] = None


class AnalysisResult(BaseModel):
    """Structured AI output model expected from Gemini synthesis."""
    project_summary: str = Field(..., description="High-level factual narrative of the project context")
    architectural_decisions: List[Finding] = Field(default_factory=list)
    active_workstreams: List[Finding] = Field(default_factory=list)
    unfinished_work: List[Finding] = Field(default_factory=list)
    blockers: List[Finding] = Field(default_factory=list)
    technical_risks: List[Finding] = Field(default_factory=list)
    fragile_modules: List[str] = Field(default_factory=list, description="Files with high churn or repeated bugs")
    continuation_roadmap: List[Finding] = Field(default_factory=list, description="Prioritized next steps")
    uncertainties: List[str] = Field(default_factory=list, description="Ambiguities or areas with incomplete evidence")
    evidence_references: List[str] = Field(default_factory=list, description="All cited source chunk IDs")
    coverage_summary: Optional[CoverageSummary] = None


def get_gemini_analysis_schema() -> Dict[str, Any]:
    """Generate OpenAPI 3.0-compliant JSON schema for Gemini responseSchema enforcement."""
    finding_schema = {
        "type": "object",
        "description": "Evidence-grounded finding",
        "properties": {
            "id": {"type": "string", "description": "Unique identifier (e.g. find_01)"},
            "category": {
                "type": "string",
                "enum": [
                    "architectural_decision",
                    "active_work",
                    "unfinished_work",
                    "blocker",
                    "technical_risk",
                    "continuation_recommendation",
                ],
            },
            "title": {"type": "string", "description": "Concise headline of the finding"},
            "description": {"type": "string", "description": "Detailed explanation based on repository activity"},
            "priority": {"type": "string", "enum": ["high", "medium", "low"]},
            "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
            "evidence_source_ids": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Source chunk IDs backing this finding",
            },
            "evidence_explanation": {
                "type": "string",
                "description": "Explanation of how cited sources support the claim",
            },
        },
        "required": ["id", "category", "title", "description", "evidence_source_ids"],
    }

    return {
        "type": "object",
        "properties": {
            "project_summary": {
                "type": "string",
                "description": "High-level factual narrative of the project context",
            },
            "architectural_decisions": {
                "type": "array",
                "items": finding_schema,
            },
            "active_workstreams": {
                "type": "array",
                "items": finding_schema,
            },
            "unfinished_work": {
                "type": "array",
                "items": finding_schema,
            },
            "blockers": {
                "type": "array",
                "items": finding_schema,
            },
            "technical_risks": {
                "type": "array",
                "items": finding_schema,
            },
            "fragile_modules": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Files with high churn or repeated bugs",
            },
            "continuation_roadmap": {
                "type": "array",
                "items": finding_schema,
            },
            "uncertainties": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Ambiguities or areas with incomplete evidence",
            },
            "evidence_references": {
                "type": "array",
                "items": {"type": "string"},
                "description": "All cited source chunk IDs",
            },
        },
        "required": ["project_summary"],
    }


class DeveloperView(BaseModel):
    """Technical handover view tailored for incoming software developers."""
    technical_architecture: List[Finding]
    active_code_work: List[Finding]
    unfinished_implementations: List[Finding]
    blockers_and_failing_areas: List[Finding]
    fragile_files: List[str]
    immediate_tasks: List[Finding]
    evidence_appendix: List[Dict[str, Any]]


class TeamLeadView(BaseModel):
    """Strategic handover view tailored for engineering leads and managers."""
    executive_summary: str
    project_health_status: str
    major_milestones_and_workstreams: List[Finding]
    critical_blockers_and_risks: List[Finding]
    strategic_priorities: List[Finding]
    coverage_overview: CoverageSummary
    uncertainties_and_open_questions: List[str]


class HandoverReportPayload(BaseModel):
    """Full persisted handover report document."""
    title: str
    repository_id: str
    repository_name: str
    analysis_run_id: str
    generated_at: str
    model_used: str
    developer_view: DeveloperView
    team_lead_view: TeamLeadView
    raw_findings: List[Finding]
    coverage: CoverageSummary
    verification_stats: Dict[str, int]


class ReportSummaryResponse(BaseModel):
    """Summary representation of a handover report."""
    id: str
    repository_id: str
    analysis_run_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    model_used: Optional[str] = None
    verification_stats: Optional[Dict[str, int]] = None


class ReportDetailResponse(BaseModel):
    """Detailed response for a single handover report."""
    id: str
    repository_id: str
    analysis_run_id: str
    title: str
    status: str
    created_at: str
    updated_at: str
    report_data: HandoverReportPayload
