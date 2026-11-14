import React from 'react';
import { TeamLeadView as TeamLeadViewType } from '../../types/api';
import { FindingCard } from './FindingCard';
import { Card, CardHeader, CardTitle, CardContent } from '../ui/Card';
import {
  AlertTriangle,
  Compass,
  FileCheck2,
  HelpCircle,
  Activity,
  Milestone,
} from 'lucide-react';

interface TeamLeadViewProps {
  data: TeamLeadViewType;
  onViewEvidence: (sourceId: string) => void;
}

export const TeamLeadView: React.FC<TeamLeadViewProps> = ({ data, onViewEvidence }) => {
  return (
    <div className="space-y-8">
      {/* 1. Executive Summary & Health Status Banner */}
      <Card className="bg-gradient-to-br from-white to-slate-50 border-slate-200">
        <CardContent className="space-y-4">
          <div className="flex items-start justify-between gap-4">
            <div>
              <span className="text-[11px] font-semibold text-brand-600 uppercase tracking-wider block mb-1">
                Executive Synthesis
              </span>
              <h3 className="text-base font-semibold text-slate-900">Project Overview</h3>
            </div>
            <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-800 border border-emerald-200">
              <Activity className="w-4 h-4 text-emerald-600" />
              <span>{data.project_health_status}</span>
            </div>
          </div>
          <p className="text-sm text-slate-700 leading-relaxed">{data.executive_summary}</p>
        </CardContent>
      </Card>

      {/* 2. Critical Blockers and Risks */}
      {data.critical_blockers_and_risks.length > 0 && (
        <section className="space-y-4">
          <div className="flex items-center gap-2 text-rose-800">
            <AlertTriangle className="w-5 h-5 text-rose-600" />
            <h3 className="text-base font-semibold">Critical Risks & Governance Blockers</h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.critical_blockers_and_risks.map((finding) => (
              <FindingCard key={finding.id} finding={finding} onViewEvidence={onViewEvidence} />
            ))}
          </div>
        </section>
      )}

      {/* 3. Strategic Continuation Priorities */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 text-slate-900">
          <Compass className="w-5 h-5 text-brand-600" />
          <h3 className="text-base font-semibold">Recommended Strategic Priorities</h3>
        </div>
        {data.strategic_priorities.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.strategic_priorities.map((finding) => (
              <FindingCard key={finding.id} finding={finding} onViewEvidence={onViewEvidence} />
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 italic bg-white p-4 rounded-lg border border-slate-200">
            No strategic priorities recorded.
          </p>
        )}
      </section>

      {/* 4. Major Workstreams & Milestones */}
      <section className="space-y-4">
        <div className="flex items-center gap-2 text-slate-900">
          <Milestone className="w-5 h-5 text-indigo-600" />
          <h3 className="text-base font-semibold">Active Milestones & Workstreams</h3>
        </div>
        {data.major_milestones_and_workstreams.length > 0 ? (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {data.major_milestones_and_workstreams.map((finding) => (
              <FindingCard key={finding.id} finding={finding} onViewEvidence={onViewEvidence} />
            ))}
          </div>
        ) : (
          <p className="text-xs text-slate-500 italic bg-white p-4 rounded-lg border border-slate-200">
            No active milestones recorded.
          </p>
        )}
      </section>

      {/* 5. Uncertainties & Open Governance Questions */}
      {data.uncertainties_and_open_questions && data.uncertainties_and_open_questions.length > 0 && (
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <HelpCircle className="w-4 h-4 text-amber-500" />
              <CardTitle>Uncertainties & Open Questions</CardTitle>
            </div>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2.5">
              {data.uncertainties_and_open_questions.map((uncertainty, index) => (
                <li key={index} className="flex items-start gap-2.5 text-xs text-slate-700">
                  <span className="w-1.5 h-1.5 rounded-full bg-amber-400 mt-1.5 shrink-0" />
                  <span>{uncertainty}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* 6. Honest History Coverage Overview */}
      {data.coverage_overview && (
        <Card className="bg-slate-50/50">
          <CardHeader>
            <div className="flex items-center gap-2">
              <FileCheck2 className="w-4 h-4 text-slate-700" />
              <CardTitle>History Analysis Coverage Metrics</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="grid grid-cols-2 md:grid-cols-4 gap-4 text-center">
            <div className="p-3 bg-white rounded border border-slate-200">
              <span className="text-[11px] text-slate-400 block">Total Chunks</span>
              <span className="text-lg font-bold text-slate-800">
                {data.coverage_overview.total_available_chunks}
              </span>
            </div>
            <div className="p-3 bg-white rounded border border-slate-200">
              <span className="text-[11px] text-slate-400 block">Analyzed Chunks</span>
              <span className="text-lg font-bold text-brand-600">
                {data.coverage_overview.analyzed_chunks}
              </span>
            </div>
            <div className="p-3 bg-white rounded border border-slate-200">
              <span className="text-[11px] text-slate-400 block">Coverage Ratio</span>
              <span className="text-lg font-bold text-slate-800">
                {data.coverage_overview.coverage_percentage}%
              </span>
            </div>
            <div className="p-3 bg-white rounded border border-slate-200">
              <span className="text-[11px] text-slate-400 block">Completeness</span>
              <span
                className={`text-xs font-semibold px-2 py-1 rounded inline-block mt-1 ${
                  data.coverage_overview.is_complete_coverage
                    ? 'bg-emerald-50 text-emerald-700'
                    : 'bg-amber-50 text-amber-800'
                }`}
              >
                {data.coverage_overview.is_complete_coverage ? '100% Complete' : 'Bounded Budget'}
              </span>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
};
