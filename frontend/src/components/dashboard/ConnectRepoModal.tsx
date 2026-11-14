import React, { useState } from 'react';
import { api, ApiError } from '../../services/api';
import { Repository } from '../../types/api';
import { Button } from '../ui/Button';
import { GitBranch, X, AlertCircle } from 'lucide-react';

interface ConnectRepoModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: (repo: Repository) => void;
}

export const ConnectRepoModal: React.FC<ConnectRepoModalProps> = ({ isOpen, onClose, onSuccess }) => {
  const [url, setUrl] = useState('');
  const [name, setName] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const trimmedUrl = url.trim();
    if (!trimmedUrl) {
      setError('Please provide a valid GitHub repository URL.');
      return;
    }

    if (!trimmedUrl.startsWith('https://github.com/')) {
      setError('Repository URL must begin with https://github.com/{owner}/{repo}');
      return;
    }

    setLoading(true);
    try {
      const repo = await api.connectRepository({
        repository_url: trimmedUrl,
        name: name.trim() || undefined,
      });
      setUrl('');
      setName('');
      onSuccess(repo);
      onClose();
    } catch (err: any) {
      if (err instanceof ApiError) {
        setError(err.detail);
      } else {
        setError(err.message || 'Failed to connect repository.');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto">
      <div className="flex min-h-screen items-center justify-center p-4">
        {/* Backdrop */}
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm transition-opacity" onClick={onClose} />

        {/* Modal Window */}
        <div className="relative w-full max-w-md bg-white rounded-xl shadow-2xl border border-slate-200 p-6 space-y-5 animate-in fade-in zoom-in-95 duration-150">
          <div className="flex items-center justify-between pb-3 border-b border-slate-100">
            <div className="flex items-center gap-2 text-slate-900">
              <div className="w-8 h-8 rounded-lg bg-brand-50 text-brand-600 flex items-center justify-center border border-brand-100">
                <GitBranch className="w-4 h-4" />
              </div>
              <h3 className="text-base font-semibold">Connect Repository</h3>
            </div>
            <button onClick={onClose} className="text-slate-400 hover:text-slate-600 p-1">
              <X className="w-5 h-5" />
            </button>
          </div>

          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                GitHub Repository URL <span className="text-rose-500">*</span>
              </label>
              <input
                type="url"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://github.com/fastapi/fastapi"
                required
                className="w-full px-3 py-2 text-xs rounded-md border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 font-mono text-slate-800"
              />
              <p className="text-[11px] text-slate-500 mt-1">
                Must be a public repository or accessible with your configured GITHUB_TOKEN.
              </p>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-700 mb-1">
                Custom Display Name (Optional)
              </label>
              <input
                type="text"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Core API Service"
                className="w-full px-3 py-2 text-xs rounded-md border border-slate-300 focus:outline-none focus:ring-2 focus:ring-brand-500 text-slate-800"
              />
            </div>

            {error && (
              <div className="rounded-md bg-rose-50 border border-rose-200 p-3 text-xs text-rose-800 flex items-start gap-2">
                <AlertCircle className="w-4 h-4 text-rose-600 shrink-0 mt-0.5" />
                <p>{error}</p>
              </div>
            )}

            <div className="pt-2 flex items-center justify-end gap-2.5">
              <Button type="button" variant="outline" size="sm" onClick={onClose} disabled={loading}>
                Cancel
              </Button>
              <Button type="submit" variant="primary" size="sm" isLoading={loading}>
                Connect Repository
              </Button>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
};
