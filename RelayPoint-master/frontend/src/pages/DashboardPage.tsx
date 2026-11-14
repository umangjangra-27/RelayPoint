import React, { useState } from 'react';
import { ActivityItem, ReportSummary, Repository } from '../types/api';
import { Card, CardHeader, CardTitle, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { ConnectRepoModal } from '../components/dashboard/ConnectRepoModal';
import { timeAgo } from '../utils/formatters';
import {
  GitBranch,
  FileText,
  Clock,
  Plus,
  ArrowRight,
  ExternalLink,
  ShieldCheck,
  DownloadCloud,
  Sparkles,
} from 'lucide-react';

interface DashboardPageProps {
  repositories: Repository[];
  reports: ReportSummary[];
  recentActivity: ActivityItem[];
  onSelectRepository: (repoId: string) => void;
  onOpenReport: (reportId: string) => void;
  onRefresh: () => void;
  onRepositoryConnected: (repo: Repository) => void;
  onIngestRepo: (repoId: string) => void;
  onAnalyzeRepo: (repoId: string) => void;
  ingestingRepoId: string | null;
  analyzingRepoId: string | null;
}

export const DashboardPage: React.FC<DashboardPageProps> = ({
  repositories,
  reports,
  recentActivity,
  onSelectRepository,
  onOpenReport,
  onRefresh,
  onRepositoryConnected,
  onIngestRepo,
  onAnalyzeRepo,
  ingestingRepoId,
  analyzingRepoId,
}) => {
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);

  return (
    <div className="space-y-8">
      {/* Overview Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-5">
        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Connected Repos
            </span>
            <div className="w-8 h-8 rounded-md bg-brand-50 text-brand-600 flex items-center justify-center border border-brand-100">
              <GitBranch className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">{repositories.length}</span>
            <span className="text-xs text-slate-400">tracked</span>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Handover Reports
            </span>
            <div className="w-8 h-8 rounded-md bg-indigo-50 text-indigo-600 flex items-center justify-center border border-indigo-100">
              <FileText className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">{reports.length}</span>
            <span className="text-xs text-slate-400">synthesized</span>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Recent Events
            </span>
            <div className="w-8 h-8 rounded-md bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100">
              <Clock className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-2xl font-bold text-slate-900">{recentActivity.length}</span>
            <span className="text-xs text-slate-400">activities</span>
          </div>
        </Card>

        <Card className="p-5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
              Evidence Engine
            </span>
            <div className="w-8 h-8 rounded-md bg-emerald-50 text-emerald-600 flex items-center justify-center border border-emerald-100">
              <ShieldCheck className="w-4 h-4" />
            </div>
          </div>
          <div className="mt-2 flex items-baseline gap-2">
            <span className="text-base font-bold text-emerald-700">Deterministic</span>
            <span className="text-xs text-slate-400">SHA-256</span>
          </div>
        </Card>
      </div>

      {/* Repositories Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between w-full">
            <div>
              <CardTitle>Connected Repositories</CardTitle>
              <p className="text-xs text-slate-500 mt-0.5">Manage repositories and trigger history ingestion.</p>
            </div>
            <Button
              variant="primary"
              size="sm"
              onClick={() => setIsConnectModalOpen(true)}
              icon={<Plus className="w-4 h-4" />}
            >
              Connect Repository
            </Button>
          </div>
        </CardHeader>

        <CardContent className="p-0">
          {repositories.length > 0 ? (
            <div className="divide-y divide-slate-100">
              {repositories.map((repo) => (
                <div
                  key={repo.id}
                  className="p-5 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-slate-50/70 transition-colors"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <button
                        onClick={() => onSelectRepository(repo.id)}
                        className="text-sm font-semibold text-slate-900 hover:text-brand-600 transition-colors hover:underline text-left"
                      >
                        {repo.full_name}
                      </button>
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-600 font-mono text-[10px]">
                        {repo.default_branch}
                      </span>
                    </div>
                    {repo.description ? (
                      <p className="text-xs text-slate-500 line-clamp-1">{repo.description}</p>
                    ) : (
                      <p className="text-xs text-slate-400 italic">No description provided</p>
                    )}
                    <span className="text-[11px] text-slate-400 block">
                      Synced {timeAgo(repo.updated_at)}
                    </span>
                  </div>

                  <div className="flex items-center gap-2.5 shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onIngestRepo(repo.id)}
                      isLoading={ingestingRepoId === repo.id}
                      icon={<DownloadCloud className="w-3.5 h-3.5 text-slate-600" />}
                    >
                      Ingest
                    </Button>

                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => onAnalyzeRepo(repo.id)}
                      isLoading={analyzingRepoId === repo.id}
                      icon={<Sparkles className="w-3.5 h-3.5 text-brand-600" />}
                    >
                      Handover
                    </Button>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onSelectRepository(repo.id)}
                      icon={<ArrowRight className="w-3.5 h-3.5" />}
                    >
                      Open
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-12 text-center text-xs text-slate-500 space-y-3">
              <GitBranch className="w-8 h-8 text-slate-300 mx-auto" />
              <div>
                <p className="font-semibold text-slate-700">No Repositories Connected</p>
                <p className="text-slate-400 mt-0.5">Connect an authorized GitHub repository to begin knowledge ingestion.</p>
              </div>
              <Button
                variant="primary"
                size="sm"
                onClick={() => setIsConnectModalOpen(true)}
                icon={<Plus className="w-3.5 h-3.5" />}
              >
                Connect First Repository
              </Button>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Two-Column Grid: Recent Handover Reports & Activity Stream */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Recent Handover Reports */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <FileText className="w-4 h-4 text-brand-600" />
              <CardTitle>Recent Handover Reports</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {reports.length > 0 ? (
              <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto">
                {reports.slice(0, 5).map((rep) => (
                  <div
                    key={rep.id}
                    className="p-4 flex items-center justify-between text-xs hover:bg-slate-50 transition-colors"
                  >
                    <div className="space-y-0.5 pr-3">
                      <button
                        onClick={() => onOpenReport(rep.id)}
                        className="font-medium text-slate-900 hover:text-brand-600 hover:underline line-clamp-1 text-left"
                      >
                        {rep.title}
                      </button>
                      <div className="flex items-center gap-2">
                        <span className="text-[11px] text-slate-400">{timeAgo(rep.created_at)}</span>
                        {rep.model_used?.toLowerCase().includes('mock') && (
                          <span className="font-semibold text-[10px] px-1.5 py-0.2 rounded bg-amber-100 text-amber-800 border border-amber-200">
                            Demo Fixture
                          </span>
                        )}
                      </div>
                    </div>

                    <Button variant="outline" size="sm" onClick={() => onOpenReport(rep.id)}>
                      View
                    </Button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-10 text-center text-xs text-slate-400 italic">
                No handover reports synthesized yet.
              </div>
            )}
          </CardContent>
        </Card>

        {/* Global Recent Activity */}
        <Card>
          <CardHeader>
            <div className="flex items-center gap-2">
              <Clock className="w-4 h-4 text-slate-600" />
              <CardTitle>Repository Activity Stream</CardTitle>
            </div>
          </CardHeader>
          <CardContent className="p-0">
            {recentActivity.length > 0 ? (
              <div className="divide-y divide-slate-100 max-h-80 overflow-y-auto">
                {recentActivity.slice(0, 8).map((act, index) => (
                  <div key={index} className="p-3.5 text-xs hover:bg-slate-50 transition-colors space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="capitalize px-1.5 py-0.5 rounded bg-slate-100 text-slate-700 text-[10px] font-medium">
                        {act.source_type}
                      </span>
                      <span className="text-slate-400 text-[11px]">{timeAgo(act.timestamp)}</span>
                    </div>
                    <p className="font-medium text-slate-800 line-clamp-1">{act.title}</p>
                    <div className="flex items-center justify-between text-[11px] text-slate-400">
                      <span>By {act.author}</span>
                      {act.source_url && (
                        <a
                          href={act.source_url}
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
              <div className="py-10 text-center text-xs text-slate-400 italic">
                No activity stream records yet.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Connect Repo Modal */}
      <ConnectRepoModal
        isOpen={isConnectModalOpen}
        onClose={() => setIsConnectModalOpen(false)}
        onSuccess={(newRepo) => {
          onRepositoryConnected(newRepo);
          onRefresh();
        }}
      />
    </div>
  );
};
