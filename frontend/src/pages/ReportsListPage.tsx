import React from 'react';
import { ReportSummary, Repository } from '../types/api';
import { Card, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { formatDate } from '../utils/formatters';
import {
  FileText,
  ShieldCheck,
  AlertTriangle,
  ArrowRight,
  GitBranch,
} from 'lucide-react';

interface ReportsListPageProps {
  reports: ReportSummary[];
  repositories: Repository[];
  onOpenReport: (reportId: string) => void;
  onSelectRepository: (repoId: string) => void;
}

export const ReportsListPage: React.FC<ReportsListPageProps> = ({
  reports,
  repositories,
  onOpenReport,
  onSelectRepository,
}) => {
  const repoMap = new Map(repositories.map((r) => [r.id, r]));

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-xl font-bold text-slate-900 tracking-tight">Synthesized Handover Reports</h2>
        <p className="text-xs text-slate-500 mt-0.5">
          Access AI-generated, evidence-linked handover reports across all tracked repositories.
        </p>
      </div>

      <Card>
        <CardContent className="p-0">
          {reports.length > 0 ? (
            <div className="divide-y divide-slate-100">
              {reports.map((rep) => {
                const repo = repoMap.get(rep.repository_id);
                const stats = rep.verification_stats || {};

                return (
                  <div
                    key={rep.id}
                    className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-50 transition-colors"
                  >
                    <div className="space-y-1.5">
                      <div className="flex items-center gap-2 flex-wrap">
                        {repo && (
                          <button
                            onClick={() => onSelectRepository(repo.id)}
                            className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 hover:bg-slate-200 text-slate-700 font-medium inline-flex items-center gap-1 transition-colors"
                          >
                            <GitBranch className="w-3 h-3 text-slate-500" />
                            {repo.full_name}
                          </button>
                        )}
                        <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-500">
                          {rep.model_used || 'Gemini'}
                        </span>
                        {rep.model_used?.toLowerCase().includes('mock') && (
                          <span className="font-semibold text-[10px] px-1.5 py-0.5 rounded bg-amber-100 text-amber-800 border border-amber-200">
                            Demonstration Data
                          </span>
                        )}
                      </div>

                      <button
                        onClick={() => onOpenReport(rep.id)}
                        className="text-base font-semibold text-slate-900 hover:text-brand-600 transition-colors hover:underline text-left"
                      >
                        {rep.title}
                      </button>

                      <div className="flex items-center gap-3 text-xs text-slate-400">
                        <span>Generated {formatDate(rep.created_at)}</span>
                        <span>•</span>
                        <span className="capitalize">{rep.status}</span>
                      </div>
                    </div>

                    <div className="flex items-center gap-4 shrink-0">
                      {/* Verification Stats Summary */}
                      <div className="flex items-center gap-2 text-xs">
                        <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-emerald-50 text-emerald-800 border border-emerald-200 text-[11px] font-medium">
                          <ShieldCheck className="w-3 h-3 text-emerald-600" />
                          {stats.SOURCE_LINKED || 0} Linked
                        </span>
                        {stats.NEEDS_HUMAN_REVIEW ? (
                          <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-amber-50 text-amber-800 border border-amber-200 text-[11px] font-medium">
                            <AlertTriangle className="w-3 h-3 text-amber-600" />
                            {stats.NEEDS_HUMAN_REVIEW} Review
                          </span>
                        ) : null}
                      </div>

                      <Button
                        variant="primary"
                        size="sm"
                        onClick={() => onOpenReport(rep.id)}
                        icon={<ArrowRight className="w-3.5 h-3.5" />}
                      >
                        Open Report
                      </Button>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="py-16 text-center text-xs text-slate-500 space-y-2">
              <FileText className="w-8 h-8 text-slate-300 mx-auto" />
              <p className="font-semibold text-slate-700">No Handover Reports Available</p>
              <p className="text-slate-400">
                Connect a repository and click "Generate Handover" to synthesize your first report.
              </p>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
};
