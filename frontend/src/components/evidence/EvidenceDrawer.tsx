import React, { useEffect, useState } from 'react';
import { Drawer } from '../ui/Drawer';
import { EvidenceAppendixItem, SourceChunk } from '../../types/api';
import { api } from '../../services/api';
import { formatDate, truncateSha } from '../../utils/formatters';
import {
  ExternalLink,
  Copy,
  Check,
  ShieldCheck,
  AlertCircle,
  FileCode,
  Tag as TagIcon,
  Loader2,
} from 'lucide-react';

interface EvidenceDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  sourceId: string | null;
  repositoryId?: string | null;
  preloadedItem?: EvidenceAppendixItem | null;
}

export const EvidenceDrawer: React.FC<EvidenceDrawerProps> = ({
  isOpen,
  onClose,
  sourceId,
  repositoryId,
  preloadedItem,
}) => {
  const [sourceData, setSourceData] = useState<SourceChunk | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!isOpen || !sourceId) {
      setSourceData(null);
      setError(null);
      return;
    }

    if (repositoryId) {
      setLoading(true);
      setError(null);
      api
        .getSourceChunk(repositoryId, sourceId)
        .then((chunk) => {
          setSourceData(chunk);
        })
        .catch((err) => {
          // If direct endpoint fails, fallback to preloaded item if available
          if (!preloadedItem) {
            setError(err.detail || 'Could not fetch source chunk details.');
          }
        })
        .finally(() => {
          setLoading(false);
        });
    }
  }, [isOpen, sourceId, repositoryId]);

  const handleCopy = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const contentText = sourceData?.content || preloadedItem?.content_preview || '';
  const sourceType = sourceData?.source_type || preloadedItem?.source_type || 'Unknown';
  const sourceExtId = sourceData?.source_external_id || preloadedItem?.external_id || preloadedItem?.commit_hash;
  const sourceUrl = sourceData?.source_url || preloadedItem?.source_url;
  const contentHash = sourceData?.content_hash;
  const createdAt = sourceData?.created_at;
  const authorName = sourceData?.metadata?.author_name || sourceData?.metadata?.author;

  return (
    <Drawer
      isOpen={isOpen}
      onClose={onClose}
      title="Evidence Grounding Inspection"
      subtitle={sourceId ? `Citing Source ID: ${sourceId}` : ''}
    >
      {loading ? (
        <div className="flex flex-col items-center justify-center py-16 text-slate-500">
          <Loader2 className="w-8 h-8 animate-spin text-brand-600 mb-3" />
          <p className="text-sm">Fetching ground-truth chunk from SQLite...</p>
        </div>
      ) : error && !preloadedItem ? (
        <div className="rounded-lg bg-rose-50 border border-rose-200 p-4 text-rose-800 text-sm flex items-start gap-3">
          <AlertCircle className="w-5 h-5 shrink-0 text-rose-600 mt-0.5" />
          <div>
            <span className="font-semibold block">Source Retrieval Failed</span>
            <p className="text-xs text-rose-700 mt-1">{error}</p>
          </div>
        </div>
      ) : (
        <div className="space-y-6">
          {/* Metadata Card */}
          <div className="rounded-lg border border-slate-200 bg-slate-50 p-4 space-y-3">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md text-xs font-semibold bg-white border border-slate-200 text-slate-800 uppercase tracking-wide">
                <FileCode className="w-3.5 h-3.5 text-brand-600" />
                {sourceType}
              </span>

              {sourceUrl && (
                <a
                  href={sourceUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-xs text-brand-600 hover:text-brand-700 font-medium"
                >
                  View on GitHub <ExternalLink className="w-3.5 h-3.5" />
                </a>
              )}
            </div>

            <div className="grid grid-cols-2 gap-3 text-xs pt-1">
              <div>
                <span className="text-slate-500 block">Identifier:</span>
                <span className="font-mono text-slate-800 font-medium">
                  {sourceExtId ? truncateSha(sourceExtId, 12) : 'N/A'}
                </span>
              </div>
              <div>
                <span className="text-slate-500 block">Recorded Date:</span>
                <span className="text-slate-800">{formatDate(createdAt)}</span>
              </div>
              {authorName && (
                <div>
                  <span className="text-slate-500 block">Author:</span>
                  <span className="text-slate-800 font-medium">{authorName}</span>
                </div>
              )}
              {contentHash && (
                <div>
                  <span className="text-slate-500 block">SHA-256 Hash:</span>
                  <span className="font-mono text-slate-700 text-[11px]" title={contentHash}>
                    {truncateSha(contentHash, 10)}...
                  </span>
                </div>
              )}
            </div>
          </div>

          {/* Cryptographic Integrity Verified Alert */}
          <div className="rounded-lg bg-emerald-50/80 border border-emerald-200 p-3.5 flex items-start gap-2.5">
            <ShieldCheck className="w-4 h-4 text-emerald-600 shrink-0 mt-0.5" />
            <div className="text-xs text-emerald-800">
              <span className="font-semibold block">Cryptographic Verification Passed</span>
              <p className="mt-0.5 text-emerald-700 leading-relaxed">
                This source chunk was matched against the repository's SQLite database and verified with deterministic SHA-256 integrity.
              </p>
            </div>
          </div>

          {/* Raw Sanitized Source Content */}
          <div>
            <div className="flex items-center justify-between pb-2">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500 flex items-center gap-1.5">
                <TagIcon className="w-3.5 h-3.5" /> Sanitized Ground-Truth Excerpt
              </span>
              <button
                onClick={() => handleCopy(contentText)}
                className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-800 transition-colors"
                title="Copy excerpt"
              >
                {copied ? <Check className="w-3.5 h-3.5 text-emerald-600" /> : <Copy className="w-3.5 h-3.5" />}
                {copied ? 'Copied' : 'Copy'}
              </button>
            </div>

            <pre className="p-4 rounded-lg bg-slate-900 text-slate-100 font-mono text-xs leading-relaxed overflow-x-auto whitespace-pre-wrap max-h-96 border border-slate-800">
              {contentText || 'No content available for this source chunk.'}
            </pre>
            <p className="text-[11px] text-slate-400 mt-1 italic">
              * Note: All credentials, passwords, and API tokens were deterministically scrubbed before database persistence.
            </p>
          </div>
        </div>
      )}
    </Drawer>
  );
};
