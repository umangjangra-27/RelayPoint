import React, { useEffect, useState } from 'react';
import { api } from '../services/api';
import { ActivityItem, ReportSummary, Repository, SourceChunk } from '../types/api';
import { Button } from '../components/ui/Button';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { formatDate, timeAgo, truncateSha } from '../utils/formatters';
import { EvidenceDrawer } from '../components/evidence/EvidenceDrawer';
import {
  GitBranch,
  ExternalLink,
  DownloadCloud,
  Sparkles,
  Layers,
  Clock,
  FileText,
  AlertCircle,
  ArrowLeft,
  Loader2,
  CheckCircle2,
} from 'lucide-react';

interface RepositoryDetailPageProps {
  repositoryId: string;
  onBack: () => void;
  onOpenReport: (reportId: string) => void;
}

export const RepositoryDetailPage: React.FC<RepositoryDetailPageProps> = ({
  repositoryId,
  onBack,
  onOpenReport,
}) => {
  const [repo, setRepo] = useState<Repository | null>(null);
  const [activity, setActivity] = useState<ActivityItem[]>([]);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [sources, setSources] = useState<SourceChunk[]>([]);
  const [totalSources, setTotalSources] = useState(0);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Ingestion & Analysis state
  const [isIngesting, setIsIngesting] = useState(false);
  const [ingestionMessage, setIngestionMessage] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [analysisError, setAnalysisError] = useState<string | null>(null);

  // Evidence Drawer state
  const [selectedSourceId, setSelectedSourceId] = useState<string | null>(null);
  const [isDrawerOpen, setIsDrawerOpen] = useState(false);

  const loadAll = () => {
    setLoading(true);
    setError(null);

    Promise.all([
      api.getRepository(repositoryId),
      api.getRepositoryActivity(repositoryId, 25),
      api.listRepositoryReports(repositoryId),
      api.getRepositorySources(repositoryId, { limit: 15 }),
    ])
      .then(([repoData, actData, repData, srcData]) => {
        setRepo(repoData);
        setActivity(actData);
        setReports(repData);
        setSources(srcData.sources);
        setTotalSources(srcData.total);
      })
      .catch((err) => {
        setError(err.detail || 'Could not load repository data.');
      })
      .finally(() => {
        setLoading(false);
      });
  };

  useEffect(() => {
    loadAll();
  }, [repositoryId]);

  const handleIngest = async () => {
    setIsIngesting(true);
    setIngestionMessage(null);
    try {
      const res = await api.ingestRepository(repositoryId);
      setIngestionMessage(`Successfully ingested ${res.chunks_created} new chunks (${res.duplicates_skipped} duplicates skipped).`);
      loadAll();
    } catch (err: any) {
      alert(`Ingestion failed: ${err.detail || err.message}`);
    } finally {
      setIsIngesting(false);
    }
  };

  const handleAnalyze = async () => {
    setIsAnalyzing(true);
    setAnalysisError(null);
    try {
      const res = await api.analyzeRepository(repositoryId);
      onOpenReport(res.report_id);
    } catch (err: any) {
      setAnalysisError(err.detail || 'Analysis failed. Please verify GEMINI_API_KEY is configured.');
    } finally {
      setIsAnalyzing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center py-24 text-slate-500">
        <Loader2 className="w-8 h-8 animate-spin text-brand-600 mb-3" />
        <p className="text-sm">Loading repository intelligence...</p>
      </div>
    );
  }

  if (error || !repo) {
    return (
      <div className="rounded-lg bg-rose-50 border border-rose-200 p-6 text-center max-w-lg mx-auto">
        <AlertCircle className="w-8 h-8 text-rose-600 mx-auto mb-2" />
        <h3 className="text-base font-semibold text-rose-900">Repository Unavailable</h3>
        <p className="text-xs text-rose-700 mt-1 mb-4">{error || 'Repository record not found.'}</p>
        <Button variant="outline" size="sm" onClick={onBack} icon={<ArrowLeft className="w-3.5 h-3.5" />}>
          Back to Repositories
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Back button */}
      <button
        onClick={onBack}
        className="inline-flex items-center gap-1.5 text-xs font-medium text-slate-500 hover:text-slate-800 transition-colors"
      >
        <ArrowLeft className="w-3.5 h-3.5" /> Back to Repositories
      </button>

      {/* Main Repository Header Card */}
      <div className="bg-white rounded-lg border border-slate-200 p-6 shadow-sm space-y-4">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div className="space-y-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-semibold uppercase">
                {repo.provider}
              </span>
              <span className="text-xs text-slate-400 font-mono flex items-center gap-1">
                <GitBranch className="w-3.5 h-3.5" /> {repo.default_branch}
              </span>
            </div>
            <h2 className="text-2xl font-bold text-slate-900 tracking-tight">{repo.full_name}</h2>
            {repo.description && <p className="text-xs text-slate-600 max-w-3xl">{repo.description}</p>}
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-2.5 shrink-0">
            <Button
              variant="outline"
              size="sm"
              onClick={handleIngest}
              isLoading={isIngesting}
              icon={<DownloadCloud className="w-4 h-4 text-slate-600" />}
              title="Pull commits, issues, and PRs, scrub secrets, and store chunks"
            >
              Ingest History
            </Button>

            <Button
              variant="primary"
              size="sm"
              onClick={handleAnalyze}
              isLoading={isAnalyzing}
              disabled={totalSources === 0}
              icon={<Sparkles className="w-4 h-4 text-white" />}
              title={totalSources === 0 ? 'Ingest history before analyzing' : 'Generate AI Handover Report'}
            >
              Generate Handover
            </Button>

            <a
              href={repo.repository_url}
              target="_blank"
              rel="noopener noreferrer"
              className="p-2 rounded-md border border-slate-200 text-slate-500 hover:text-slate-800 hover:bg-slate-50 transition-colors"
              title="Open repository on GitHub"
            >
              <ExternalLink className="w-4 h-4" />
            </a>
          </div>
        </div>

        {/* Feedback Messages */}
        {ingestionMessage && (
          <div className="rounded bg-emerald-50 border border-emerald-200 p-3 text-xs text-emerald-800 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-600 shrink-0" />
            <span>{ingestionMessage}</span>
          </div>
        )}

        {analysisError && (
          <div className="rounded bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800 flex items-start gap-2">
            <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
            <div>
              <span className="font-semibold">Analysis Notice</span>
              <p className="mt-0.5 text-rose-700">{analysisError}</p>
            </div>
          </div>
        )}

        {/* Stats Row */}
        <div className="pt-4 border-t border-slate-100 grid grid-cols-2 md:grid-cols-4 gap-4 text-xs">
          <div>
            <span className="text-slate-400 block">Sanitized Sources:</span>
            <span className="font-semibold text-slate-800 text-sm">{totalSources} stored</span>
          </div>
          <div>
            <span className="text-slate-400 block">Generated Reports:</span>
            <span className="font-semibold text-slate-800 text-sm">{reports.length} reports</span>
          </div>
          <div>
            <span className="text-slate-400 block">Connected:</span>
            <span className="text-slate-700">{formatDate(repo.created_at)}</span>
          </div>
          <div>
            <span className="text-slate-400 block">Last Activity Sync:</span>
            <span className="text-slate-700">{timeAgo(repo.updated_at)}</span>
          </div>
        </div>
      </div>

      {/* Reports Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-brand-600" />
            <CardTitle>Synthesized Handover Reports ({reports.length})</CardTitle>
          </div>
        </CardHeader>
        <CardContent className="p-0">
          {reports.length > 0 ? (
            <div className="divide-y divide-slate-100">
              {reports.map((rep) => (
                <div
                  key={rep.id}
                  className="p-4 flex items-center justify-between hover:bg-slate-50 transition-colors"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => onOpenReport(rep.id)}
                        className="text-sm font-semibold text-slate-900 hover:text-brand-600 hover:underline"
                      >
                        {rep.title}
                      </button>
                      <span className="font-mono text-[10px] px-1.5 py-0.5 rounded bg-slate-100 text-slate-600">
                        {rep.model_used || 'Gemini'}
                      </span>
                    </div>
                    <p className="text-xs text-slate-400">Created {formatDate(rep.created_at)}</p>
                  </div>

                  <div className="flex items-center gap-3">
                    {rep.verification_stats && (
                      <div className="hidden sm:flex items-center gap-2 text-xs">
                        <span className="text-emerald-700 bg-emerald-50 px-2 py-0.5 rounded border border-emerald-200">
                          {rep.verification_stats.SOURCE_LINKED || 0} Linked
                        </span>
                        {rep.verification_stats.NEEDS_HUMAN_REVIEW ? (
                          <span className="text-amber-800 bg-amber-50 px-2 py-0.5 rounded border border-amber-200">
                            {rep.verification_stats.NEEDS_HUMAN_REVIEW} Review
                          </span>
                        ) : null}
                      </div>
                    )}
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onOpenReport(rep.id)}
                    >
                      Open Report
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="p-8 text-center text-xs text-slate-500">
              <Sparkles className="w-6 h-6 text-slate-300 mx-auto mb-2" />
              <p>No handover reports synthesized yet for this repository.</p>
              <p className="text-slate-400 mt-1">Click "Generate Handover" above to analyze the repository history.</p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Two Column Layout: Ingested Sources & Activity Timeline */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Ingested Sources Snippet */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Layers className="w-4 h-4 text-indigo-600" />
              <CardTitle>Ingested Source Chunks ({totalSources})</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {sources.length > 0 ? (
              <div className="divide-y divide-slate-100 max-h-96 overflow-y-auto">
                {sources.map((src) => (
                  <div
                    key={src.id}
                    className="p-3.5 flex items-center justify-between text-xs hover:bg-slate-50 transition-colors"
                  >
                    <div className="space-y-1 pr-2">
                      <div className="flex items-center gap-2">
                        <span className="font-mono text-[11px] font-semibold text-slate-700">
                          {src.id}
                        </span>
                        <span className="capitalize px-1.5 py-0.2 rounded bg-slate-100 text-slate-600 text-[10px]">
                          {src.source_type}
                        </span>
                        {src.source_external_id && (
                          <span className="font-mono text-slate-400 text-[10px]">
                            #{truncateSha(src.source_external_id, 8)}
                          </span>
                        )}
                      </div>
                      <p className="text-slate-500 line-clamp-1 font-mono text-[11px]">
                        {src.content}
                      </p>
                    </div>

                    <button
                      onClick={() => {
                        setSelectedSourceId(src.id);
                        setIsDrawerOpen(true);
                      }}
                      className="shrink-0 px-2.5 py-1 rounded border border-slate-200 text-slate-700 hover:bg-slate-100 text-xs font-medium"
                    >
                      Inspect
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 text-center text-xs text-slate-400 italic">
                No sources ingested. Click "Ingest History" to pull commits, issues, and PRs.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Real Activity Timeline */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-700" />
              <CardTitle>Recent Project Activity ({activity.length})</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {activity.length > 0 ? (
              <div className="divide-y divide-slate-100 max-h-96 overflow-y-auto">
                {activity.map((item, idx) => (
                  <div key={idx} className="p-3.5 text-xs hover:bg-slate-50 transition-colors space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="capitalize px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-medium">
                        {item.source_type}
                      </span>
                      <span className="text-slate-400 text-[11px]">{timeAgo(item.timestamp)}</span>
                    </div>
                    <p className="font-medium text-slate-800 line-clamp-1">{item.title}</p>
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>By {item.author}</span>
                      {item.source_url && (
                        <a
                          href={item.source_url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-brand-600 hover:underline inline-flex items-center gap-0.5"
                        >
                          GitHub <ExternalLink className="w-3 h-3" />
                        </a>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="p-6 text-center text-xs text-slate-400 italic">
                No activity stream records yet. Ingest history to populate activity.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Evidence Drawer */}
      <EvidenceDrawer
        isOpen={isDrawerOpen}
        onClose={() => setIsDrawerOpen(false)}
        sourceId={selectedSourceId}
        repositoryId={repositoryId}
      />
    </div>
  );
};
