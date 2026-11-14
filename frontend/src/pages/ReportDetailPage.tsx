import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { HandoverReportPayload, ReportDetail } from '../types/api';
import { DeveloperView } from '../components/reports/DeveloperView';
import { TeamLeadView } from '../components/reports/TeamLeadView';
import { EvidenceDrawer } from '../components/evidence/EvidenceDrawer';
import { Button } from '../components/ui/Button';
import { formatDate } from '../utils/formatters';
import {
  UserCheck,
  Code,
  ShieldCheck,
  AlertTriangle,
  ArrowLeft,
  RotateCw,
  Loader2,
  AlertCircle,
  HelpCircle,
  XCircle,
} from 'lucide-react';

interface ReportDetailPageProps {
  reportId: string;
  onBack: () => void;
  onSelectRepository?: (repoId: string) => void;
}

export const ReportDetailPage: React.FC<ReportDetailPageProps> = ({
  reportId,
  onBack,
  onSelectRepository,
}) => {
  const [report, setReport] = useState<ReportDetail | null>(null);
  const [activeRole, setActiveRole] = useState<'developer' | 'team_lead'>('developer');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Evidence Drawer state
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);
  const [isReverifying, setIsReverifying] = useState(false);

  const fetchReport = () => {
    setLoading(true);
    setError(null);
    api
      .getReport(reportId)
      .then((data) => {
        setReport(data);
      })
      .catch((err) => {
        setError(err.detail || 'Could not load handover report.');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    fetchReport();
  }, [reportId]);

  const handleReverify = () => {
    setIsReverifying(true);
    api
      .verifyReport(reportId)
      .then(() => {
        fetchReport();
      })
      .catch((err) => {
        alert(`Reverification failed: ${err.detail || err.message}`);
      })
      .finally(() => {
        setIsReverifying(false);
      });
  };

  const handleOpenEvidence = (sourceId: string) => {
    setSelectedSourceId(sourceId);
    setIsDrawerOpen(true);
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-slate-500">
        <Loader2 className="w-8 h-8 animate-spin text-brand-600 mb-3" />
        <p className="text-sm">Retrieving structured handover report...</p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="rounded-lg bg-rose-50 border border-rose-200 p-6 text-center max-w-lg mx-auto">
        <AlertCircle className="w-8 h-8 text-rose-600 mx-auto mb-2" />
        <h3 className="text-base font-semibold text-rose-900">Failed to Load Report</h3>
        <p className="text-xs text-rose-700 mt-1 mb-4">{error || 'Report not found.'}</p>
        <Button variant="outline" size="sm" onClick={onBack} icon={<ArrowLeft className="w-3.5 h-3.5" />}>
          Back to Reports
        </Button>
      </div>
    );
  }

  const payload: HandoverReportPayload = report.report_data;
  const coverage = payload.coverage;
  const stats = payload.verification_stats || {};

  return (
    <div className="space-y-6">
      {/* Navigation & Header */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBack}
          className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
        >
          <ArrowLeft className="w-3.5 h-3.5" /> Back to Reports
        </button>

        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={handleReverify}
            isLoading={isReverifying}
            icon={<RotateCw className={`w-3.5 h-3.5 ${isReverifying ? 'animate-spin' : ''}`} />}
            title="Re-run deterministic verification against current stored sources"
          >
            Re-verify Citations
          </Button>
        </div>
      </div>

      {/* Main Report Title Banner */}
      <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-sm space-y-4">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 mb-1 flex-wrap">
              {onSelectRepository ? (
                <button
                  type="button"
                  onClick={() => onSelectRepository(report.repository_id)}
                  className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 hover:bg-slate-200 text-brand-700 font-medium transition-colors"
                  title="View repository activity and history"
                >
                  {payload.repository_name}
                </button>
              ) : (
                <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-medium">
                  {payload.repository_name}
                </span>
              )}
              <span className="text-xs text-slate-400">• Generated {formatDate(payload.generated_at)}</span>
              <span className="text-xs text-slate-400 font-mono">• {payload.model_used}</span>
              {payload.model_used?.toLowerCase().includes('mock') && (
                <span className="inline-flex items-center gap-1 font-semibold text-[11px] px-2 py-0.5 rounded bg-amber-100 text-amber-900 border border-amber-300">
                  Demonstration Report
                </span>
              )}
            </div>
            <h2 className="text-xl font-bold text-slate-900 tracking-tight">{payload.title}</h2>
          </div>

          {/* Role Switcher Toggle */}
          <div className="inline-flex p-1 bg-slate-100 rounded-lg border border-slate-200 shrink-0 self-start lg:self-center">
            <button
              onClick={() => setActiveRole('developer')}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-md text-xs font-semibold transition-all ${
                activeRole === 'developer'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <Code className="w-3.5 h-3.5 text-brand-600" />
              <span>Developer View</span>
            </button>
            <button
              onClick={() => setActiveRole('team_lead')}
              className={`inline-flex items-center gap-2 px-4 py-2 rounded-md text-xs font-semibold transition-all ${
                activeRole === 'team_lead'
                  ? 'bg-white text-slate-900 shadow-sm'
                  : 'text-slate-600 hover:text-slate-900'
              }`}
            >
              <UserCheck className="w-3.5 h-3.5 text-indigo-600" />
              <span>Team Lead View</span>
            </button>
          </div>
        </div>

        {/* Verification & Coverage Metrics Bar */}
        <div className="pt-4 border-t border-slate-100 grid grid-cols-2 md:grid-cols-5 gap-3 text-xs">
          <div className="p-2.5 rounded bg-slate-50 border border-slate-200/80">
            <span className="text-[11px] text-slate-500 block">History Coverage</span>
            <span className="font-semibold text-slate-800 text-sm">
              {coverage ? `${coverage.coverage_percentage}%` : 'N/A'}
            </span>
          </div>

          <div className="p-2.5 rounded bg-emerald-50/60 border border-emerald-200/80">
            <span className="text-[11px] text-emerald-700 block flex items-center gap-1">
              <ShieldCheck className="w-3 h-3 text-emerald-600" /> Source Linked
            </span>
            <span className="font-semibold text-emerald-800 text-sm">
              {stats.SOURCE_LINKED || 0} claims
            </span>
          </div>

          <div className="p-2.5 rounded bg-amber-50/60 border border-amber-200/80">
            <span className="text-[11px] text-amber-800 block flex items-center gap-1">
              <AlertTriangle className="w-3 h-3 text-amber-600" /> Needs Review
            </span>
            <span className="font-semibold text-amber-900 text-sm">
              {stats.NEEDS_HUMAN_REVIEW || 0} claims
            </span>
          </div>

          <div className="p-2.5 rounded bg-slate-50 border border-slate-200/80">
            <span className="text-[11px] text-slate-500 block flex items-center gap-1">
              <HelpCircle className="w-3 h-3 text-slate-400" /> No Direct Evidence
            </span>
            <span className="font-semibold text-slate-700 text-sm">
              {stats.INSUFFICIENT_EVIDENCE || 0} claims
            </span>
          </div>

          <div className="p-2.5 rounded bg-rose-50/60 border border-rose-200/80">
            <span className="text-[11px] text-rose-700 block flex items-center gap-1">
              <XCircle className="w-3 h-3 text-rose-600" /> Invalid Citation
            </span>
            <span className="font-semibold text-rose-800 text-sm">
              {stats.INVALID_REFERENCE || 0} claims
            </span>
          </div>
        </div>

        {/* Honest Coverage Warning if Bounded */}
        {coverage && !coverage.is_complete_coverage && (
          <div className="rounded bg-amber-50/90 border border-amber-200 p-3 text-xs text-amber-800 flex items-start gap-2">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Partial History Coverage ({coverage.coverage_percentage}%)</span>
              <p className="mt-0.5 text-amber-700">
                The repository history exceeded the input character budget. Analyzed {coverage.analyzed_chunks} of {coverage.total_available_chunks} total chunks. Findings reflect prioritized active work and recent commits.
              </p>
            </div>
          </div>
        )}
      </div>

      {/* Role-Based View Switch */}
      {activeRole === 'developer' ? (
        <DeveloperView data={payload.developer_view} onViewEvidence={handleOpenEvidence} />
      ) : (
        <TeamLeadView data={payload.team_lead_view} onViewEvidence={handleOpenEvidence} />
      )}

      {/* Interactive Evidence Inspection Drawer */}
      <EvidenceDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        sourceId={selectedSourceId}
        repositoryId={payload.repository_id}
        preloadedItem={
          payload.developer_view?.evidence_appendix?.find((item) => item.source_id === selectedSourceId) || null
        }
      />
    </div>
  );
};
