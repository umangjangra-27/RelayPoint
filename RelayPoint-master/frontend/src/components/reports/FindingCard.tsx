import React from 'react';
import { Finding } from '../../types/api';
import { PriorityBadge, VerificationBadge } from '../ui/Badge';
import { FileSearch, AlertTriangle } from 'lucide-react';

interface FindingCardProps {
  finding: Finding;
  onViewEvidence: (sourceId: string) => void;
}

export const FindingCard: React.FC<FindingCardProps> = ({ finding, onViewEvidence }) => {
  const hasEvidence = finding.evidence_source_ids && finding.evidence_source_ids.length > 0;

  return (
    <div className="bg-white rounded-lg border border-slate-200 p-5 shadow-sm hover:border-slate-300 transition-all space-y-3">
      {/* Top Header Row */}
      <div className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="font-mono text-xs font-semibold text-slate-500 uppercase tracking-wide">
              {finding.id}
            </span>
            <PriorityBadge priority={finding.priority} />
            <span className="text-xs text-slate-400 capitalize">• {finding.category.replace(/_/g, ' ')}</span>
          </div>
          <h4 className="text-sm font-semibold text-slate-900 leading-snug">{finding.title}</h4>
        </div>

        {/* Verification Status Badge */}
        <VerificationBadge status={finding.verification_status} />
      </div>

      {/* Main Narrative Description */}
      <p className="text-xs text-slate-600 leading-relaxed">{finding.description}</p>

      {/* Temporal Conflict Alert */}
      {finding.temporal_conflict_detected && (
        <div className="rounded bg-amber-50 border border-amber-200/80 p-2.5 text-xs text-amber-800 flex items-start gap-2">
          <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
          <div>
            <span className="font-semibold block">Temporal Discrepancy Flagged</span>
            <p className="text-[11px] text-amber-700 mt-0.5">{finding.verification_notes}</p>
          </div>
        </div>
      )}

      {/* Evidence Citations Footer */}
      <div className="pt-2 border-t border-slate-100 flex items-center justify-between text-xs">
        <div className="flex items-center gap-2">
          <span className="text-slate-400">Confidence:</span>
          <span className="font-medium text-slate-700 capitalize">{finding.confidence}</span>
        </div>

        {hasEvidence ? (
          <div className="flex items-center gap-1.5 flex-wrap">
            <span className="text-[11px] text-slate-400">Cited Evidence:</span>
            {finding.evidence_source_ids.map((sid) => (
              <button
                key={sid}
                onClick={() => onViewEvidence(sid)}
                className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-brand-50 hover:bg-brand-100 text-brand-700 font-mono text-[11px] font-medium border border-brand-200 transition-colors"
                title={`Inspect supporting evidence ${sid}`}
              >
                <FileSearch className="w-3 h-3 text-brand-600" />
                <span>{sid}</span>
              </button>
            ))}
          </div>
        ) : (
          <span className="text-[11px] text-slate-400 italic">No supporting sources cited</span>
        )}
      </div>
    </div>
  );
};
