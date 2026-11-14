import React, { useState } from 'react';
import { Repository } from '../types/api';
import { Card, CardContent } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { ConnectRepoModal } from '../components/dashboard/ConnectRepoModal';
import { formatDate, timeAgo } from '../utils/formatters';
import {
  GitBranch,
  Plus,
  ArrowRight,
  DownloadCloud,
  Sparkles,
  Search,
} from 'lucide-react';

interface RepositoriesPageProps {
  repositories: Repository[];
  onSelectRepository: (repoId: string) => void;
  onRefresh: () => void;
  onRepositoryConnected: (repo: Repository) => void;
  onIngestRepo: (repoId: string) => void;
  onAnalyzeRepo: (repoId: string) => void;
  ingestingRepoId: string | null;
  analyzingRepoId: string | null;
}

export const RepositoriesPage: React.FC<RepositoriesPageProps> = ({
  repositories,
  onSelectRepository,
  onRefresh,
  onRepositoryConnected,
  onIngestRepo,
  onAnalyzeRepo,
  ingestingRepoId,
  analyzingRepoId,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [isConnectModalOpen, setIsConnectModalOpen] = useState(false);

  const filtered = repositories.filter((r) =>
    r.full_name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (r.description && r.description.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-bold text-slate-900 tracking-tight">Connected Repositories</h2>
          <p className="text-xs text-slate-500 mt-0.5">Manage repositories and trigger automated history ingestion.</p>
        </div>

        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="w-3.5 h-3.5 absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              placeholder="Filter repositories..."
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
              className="pl-8 pr-3 py-1.5 text-xs rounded-md border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 w-48 sm:w-64"
            />
          </div>

          <Button
            variant="primary"
            size="sm"
            onClick={() => setIsConnectModalOpen(true)}
            icon={<Plus className="w-4 h-4" />}
          >
            Connect
          </Button>
        </div>
      </div>

      <Card>
        <CardContent className="p-0">
          {filtered.length > 0 ? (
            <div className="divide-y divide-slate-100">
              {filtered.map((repo) => (
                <div
                  key={repo.id}
                  className="p-5 flex flex-col md:flex-row md:items-center justify-between gap-4 hover:bg-slate-50 transition-colors"
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2 flex-wrap">
                      <button
                        onClick={() => onSelectRepository(repo.id)}
                        className="text-base font-semibold text-slate-900 hover:text-brand-600 transition-colors hover:underline text-left"
                      >
                        {repo.full_name}
                      </button>
                      <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 font-mono text-[10px]">
                        {repo.default_branch}
                      </span>
                    </div>

                    {repo.description ? (
                      <p className="text-xs text-slate-600 max-w-2xl">{repo.description}</p>
                    ) : (
                      <p className="text-xs text-slate-400 italic">No description provided</p>
                    )}

                    <div className="flex items-center gap-4 text-[11px] text-slate-400 pt-1">
                      <span>Connected {formatDate(repo.created_at)}</span>
                      <span>•</span>
                      <span>Last Activity {timeAgo(repo.updated_at)}</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-2.5 shrink-0">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onIngestRepo(repo.id)}
                      isLoading={ingestingRepoId === repo.id}
                      icon={<DownloadCloud className="w-3.5 h-3.5 text-slate-600" />}
                    >
                      Ingest History
                    </Button>

                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => onAnalyzeRepo(repo.id)}
                      isLoading={analyzingRepoId === repo.id}
                      icon={<Sparkles className="w-3.5 h-3.5 text-brand-600" />}
                    >
                      Generate Handover
                    </Button>

                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => onSelectRepository(repo.id)}
                      icon={<ArrowRight className="w-3.5 h-3.5" />}
                    >
                      Details
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="py-16 text-center text-xs text-slate-500 space-y-3">
              <GitBranch className="w-8 h-8 text-slate-300 mx-auto" />
              <p>No repositories match your filter.</p>
            </div>
          )}
        </CardContent>
      </Card>

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
