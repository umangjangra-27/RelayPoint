import React from 'react';
import { DeveloperView as DeveloperViewType } from '../../types/api';
import { FindingCard } from './FindingCard';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import { Code2, GitPullRequest, AlertOctagon, CheckSquare, FileWarning, ExternalLink, ShieldCheck } from 'lucide-react';

interface DeveloperViewProps {
  data: DeveloperViewType;
  onViewEvidence: (sourceId: string) => void;
}

export const DeveloperView: React.FC<DeveloperViewProps> = ({ data, onViewEvidence }) => {
  return (
    <div className="space-y-8">
      {/* 1. Immediate Actionable Tasks */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 text-slate-900">
          <CheckSquare className="w-5 h-5 text-brand-600" />
          <h3 className="text-base font-semibold">Immediate Developer Tasks & Continuation Roadmap</h3>
        </div>
        {data.immediate_tasks.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.immediate_tasks.map((finding) => (
              <FindingCard key={finding.id} finding={finding} onViewEvidence={onViewEvidence} />
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 italic bg-white p-4 rounded-lg border border-slate-200">
            No continuation roadmap items recorded.
          </p>
        )}
      </section>

      {/* 2. Blockers and Failing Areas */}
      {data.blockers_and_failing_areas.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-center gap-2 text-rose-700">
            <AlertOctagon className="w-5 h-5" />
            <h3 className="text-base font-semibold">Active Blockers & Failing Areas</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.blockers_and_failing_areas.map((finding) => (
              <FindingCard key={finding.id} finding={finding} onViewEvidence={onViewEvidence} />
            ))}
          </div>
        </section>
      )}

      {/* 3. Unfinished Implementation Work */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 text-slate-900">
          <GitPullRequest className="w-5 h-5 text-amber-600" />
          <h3 className="text-base font-semibold">Unfinished Work & Open Implementations</h3>
        </div>
        {data.unfinished_implementations.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.unfinished_implementations.map((finding) => (
              <FindingCard key={finding.id} finding={finding} onViewEvidence={onViewEvidence} />
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 italic bg-white p-4 rounded-lg border border-slate-200">
            No open unfinished implementations recorded in the evidence.
          </p>
        )}
      </section>

      {/* 4. Active Code Workstreams */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 text-slate-900">
          <Code2 className="w-5 h-5 text-indigo-600" />
          <h3 className="text-base font-semibold">Active Development Workstreams</h3>
        </div>
        {data.active_code_work.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.active_code_work.map((finding) => (
              <FindingCard key={finding.id} finding={finding} onViewEvidence={onViewEvidence} />
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 italic bg-white p-4 rounded-lg border border-slate-200">
            No active workstreams identified.
          </p>
        )}
      </section>

      {/* 5. Technical Architecture Decisions */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 text-slate-900">
          <Code2 className="w-5 h-5 text-slate-700" />
          <h3 className="text-base font-semibold">Architecture & Design Decisions</h3>
        </div>
        {data.technical_architecture.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.technical_architecture.map((finding) => (
              <FindingCard key={finding.id} finding={finding} onViewEvidence={onViewEvidence} />
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 italic bg-white p-4 rounded-lg border border-slate-200">
            No architectural decisions recorded in the analyzed context.
          </p>
        )}
      </section>

      {/* 6. Fragile Modules Hotspots */}
      {data.fragile_files && data.fragile_files.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <FileWarning className="w-4 h-4 text-amber-500" />
              <CardTitle>Fragile Modules & High-Churn Files</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <p className="text-xs text-slate-600 mb-3">
              The following files exhibited repeated churn or frequent modifications in the commit history:
            </p>
            <div className="flex flex-wrap gap-2">
              {data.fragile_files.map((file) => (
                <span
                  key={file}
                  className="px-2.5 py-1 rounded bg-slate-100 border border-slate-200 font-mono text-xs text-slate-800"
                >
                  {file}
                </span>
              ))}
            </div>
          </CardContent>
        </Card>
      )}

      {/* 7. Evidence Appendix */}
      {data.evidence_appendix && data.evidence_appendix.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-emerald-600" />
              <CardTitle>Evidence Appendix ({data.evidence_appendix.length} ground-truth artifacts)</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="divide-y divide-slate-100 p-0">
            {data.evidence_appendix.map((item) => (
              <div key={item.source_id} className="p-4 flex items-center justify-between text-xs hover:bg-slate-50 transition-colors">
                <div className="space-y-1">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => onViewEvidence(item.source_id)}
                      className="font-mono font-semibold text-brand-600 hover:text-brand-700 hover:underline"
                    >
                      {item.source_id}
                    </button>
                    <span className="capitalize px-2 py-0.5 rounded bg-slate-100 text-slate-600 text-[11px]">
                      {item.source_type}
                    </span>
                    {item.external_id && (
                      <span className="font-mono text-slate-500 text-[11px]">#{item.external_id}</span>
                    )}
                  </div>
                  <p className="text-slate-600 line-clamp-1 max-w-2xl font-mono text-[11px]">
                    {item.content_preview}
                  </p>
                </div>

                <div className="flex items-center gap-3">
                  {item.source_url && (
                    <a
                      href={item.source_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-slate-400 hover:text-brand-600 p-1"
                      title="Open source URL"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                    </a>
                  )}
                  <button
                    onClick={() => onViewEvidence(item.source_id)}
                    className="px-2.5 py-1 rounded border border-slate-200 text-slate-700 hover:bg-slate-100 font-medium text-xs"
                  >
                    Inspect
                  </button>
                </div>
              </div>
            ))}
          </CardContent>
        </Card>
      )}
    </div>
  );
};
