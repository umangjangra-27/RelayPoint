/**
 * RelayPoint API TypeScript Contracts.
 * Strictly aligned with FastAPI Pydantic v2 schemas.
 */

export interface HealthStatus {
  status: 'healthy' | 'degraded';
  app_name: string;
  version: string;
  database: 'connected' | 'disconnected';
}

export interface Repository {
  id: string;
  provider: string;
  external_repository_id?: string | null;
  name: string;
  full_name: string;
  description?: string;
  default_branch: string;
  repository_url: string;
  created_at: string;
  updated_at: string;
}

export interface ConnectRepositoryPayload {
  repository_url: string;
  name?: string;
}

export interface IngestionResult {
  run_id: string;
  repository_id: string;
  status: 'completed' | 'failed' | 'running';
  chunks_created: number;
  duplicates_skipped: number;
  started_at: string;
  completed_at: string;
}

export interface SourceChunk {
  id: string;
  repository_id: string;
  source_type: 'commit' | 'issue' | 'pull_request' | 'file' | string;
  source_external_id?: string | null;
  commit_hash?: string | null;
  content: string;
  content_hash: string;
  source_url?: string | null;
  metadata: Record<string, any>;
  created_at: string;
}

export interface SourceChunksResponse {
  repository_id: string;
  total: number;
  limit: number;
  offset: number;
  sources: SourceChunk[];
}

export interface ActivityItem {
  source_id: string;
  source_type: string;
  identifier?: string | null;
  title: string;
  author: string;
  timestamp?: string | null;
  source_url?: string | null;
}

export type FindingCategory =
  | 'architectural_decision'
  | 'active_work'
  | 'unfinished_work'
  | 'blocker'
  | 'technical_risk'
  | 'continuation_recommendation';

export type PriorityLevel = 'high' | 'medium' | 'low';
export type ConfidenceLevel = 'high' | 'medium' | 'low';
export type VerificationStatus =
  | 'SOURCE_LINKED'
  | 'INVALID_REFERENCE'
  | 'INSUFFICIENT_EVIDENCE'
  | 'NEEDS_HUMAN_REVIEW';

export interface Finding {
  id: string;
  category: FindingCategory;
  title: string;
  description: string;
  priority: PriorityLevel;
  confidence: ConfidenceLevel;
  evidence_source_ids: string[];
  evidence_explanation: string;
  verification_status: VerificationStatus;
  verification_notes?: string | null;
  temporal_conflict_detected?: boolean;
}

export interface CoverageSummary {
  total_available_chunks: number;
  analyzed_chunks: number;
  is_complete_coverage: boolean;
  coverage_percentage: number;
  oldest_chunk_date?: string | null;
  newest_chunk_date?: string | null;
}

export interface EvidenceAppendixItem {
  source_id: string;
  source_type?: string;
  external_id?: string;
  commit_hash?: string;
  source_url?: string;
  content_preview?: string;
  metadata?: Record<string, any>;
  verified: boolean;
  error?: string;
}

export interface DeveloperView {
  technical_architecture: Finding[];
  active_code_work: Finding[];
  unfinished_implementations: Finding[];
  blockers_and_failing_areas: Finding[];
  fragile_files: string[];
  immediate_tasks: Finding[];
  evidence_appendix: EvidenceAppendixItem[];
}

export interface TeamLeadView {
  executive_summary: string;
  project_health_status: string;
  major_milestones_and_workstreams: Finding[];
  critical_blockers_and_risks: Finding[];
  strategic_priorities: Finding[];
  coverage_overview: CoverageSummary;
  uncertainties_and_open_questions: string[];
}

export interface HandoverReportPayload {
  title: string;
  repository_id: string;
  repository_name: string;
  analysis_run_id: string;
  generated_at: string;
  model_used: string;
  developer_view: DeveloperView;
  team_lead_view: TeamLeadView;
  raw_findings: Finding[];
  coverage: CoverageSummary;
  verification_stats: Record<string, number>;
}

export interface ReportSummary {
  id: string;
  repository_id: string;
  analysis_run_id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
  model_used?: string | null;
  verification_stats?: Record<string, number> | null;
}

export interface ReportDetail {
  id: string;
  repository_id: string;
  analysis_run_id: string;
  title: string;
  status: string;
  created_at: string;
  updated_at: string;
  report_data: HandoverReportPayload;
}
