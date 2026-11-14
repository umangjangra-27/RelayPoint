/**
 * Formatting and visual mapping helpers for RelayPoint.
 */

import { PriorityLevel, VerificationStatus } from '../types/api';

export function formatDate(isoString?: string | null): string {
  if (!isoString) return 'Unknown';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleDateString('en-US', {
      month: 'short',
      day: 'numeric',
      year: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}

export function timeAgo(isoString?: string | null): string {
  if (!isoString) return 'N/A';
  try {
    const d = new Date(isoString);
    const now = new Date();
    const diffSec = Math.floor((now.getTime() - d.getTime()) / 1000);
    if (isNaN(diffSec)) return isoString;

    if (diffSec < 60) return 'Just now';
    if (diffSec < 3600) return `${Math.floor(diffSec / 60)}m ago`;
    if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}h ago`;
    if (diffSec < 604800) return `${Math.floor(diffSec / 86400)}d ago`;
    return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  } catch {
    return isoString;
  }
}

export function truncateSha(sha?: string | null, length = 7): string {
  if (!sha) return '';
  return sha.length > length ? sha.substring(0, length) : sha;
}

export function getVerificationBadgeStyle(status: VerificationStatus): {
  bg: string;
  text: string;
  border: string;
  label: string;
  icon: string;
} {
  switch (status) {
    case 'SOURCE_LINKED':
      return {
        bg: 'bg-emerald-50',
        text: 'text-emerald-700',
        border: 'border-emerald-200',
        label: 'Source Linked',
        icon: 'CheckCircle2',
      };
    case 'NEEDS_HUMAN_REVIEW':
      return {
        bg: 'bg-amber-50',
        text: 'text-amber-800',
        border: 'border-amber-200',
        label: 'Needs Review',
        icon: 'AlertTriangle',
      };
    case 'INSUFFICIENT_EVIDENCE':
      return {
        bg: 'bg-slate-50',
        text: 'text-slate-600',
        border: 'border-slate-200',
        label: 'No Direct Evidence',
        icon: 'HelpCircle',
      };
    case 'INVALID_REFERENCE':
      return {
        bg: 'bg-rose-50',
        text: 'text-rose-700',
        border: 'border-rose-200',
        label: 'Invalid Reference',
        icon: 'XCircle',
      };
    default:
      return {
        bg: 'bg-slate-50',
        text: 'text-slate-600',
        border: 'border-slate-200',
        label: status,
        icon: 'Info',
      };
  }
}

export function getPriorityBadgeStyle(priority: PriorityLevel): {
  bg: string;
  text: string;
  border: string;
} {
  switch (priority) {
    case 'high':
      return { bg: 'bg-rose-50', text: 'text-rose-700', border: 'border-rose-200' };
    case 'medium':
      return { bg: 'bg-amber-50', text: 'text-amber-700', border: 'border-amber-200' };
    case 'low':
      return { bg: 'bg-slate-100', text: 'text-slate-600', border: 'border-slate-200' };
  }
}
