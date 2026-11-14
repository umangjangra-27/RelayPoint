import React from 'react';
import { PriorityLevel, VerificationStatus } from '../../types/api';
import { getPriorityBadgeStyle, getVerificationBadgeStyle } from '../../utils/formatters';
import { CheckCircle2, AlertTriangle, HelpCircle, XCircle } from 'lucide-react';

interface VerificationBadgeProps {
  status: VerificationStatus;
  showIcon?: boolean;
  className?: string;
}

export const VerificationBadge: React.FC<VerificationBadgeProps> = ({ status, showIcon = true, className = '' }) => {
  const style = getVerificationBadgeStyle(status);

  const renderIcon = () => {
    switch (status) {
      case 'SOURCE_LINKED':
        return <CheckCircle2 className="w-3.5 h-3.5 mr-1" />;
      case 'NEEDS_HUMAN_REVIEW':
        return <AlertTriangle className="w-3.5 h-3.5 mr-1" />;
      case 'INVALID_REFERENCE':
        return <XCircle className="w-3.5 h-3.5 mr-1" />;
      case 'INSUFFICIENT_EVIDENCE':
      default:
        return <HelpCircle className="w-3.5 h-3.5 mr-1" />;
    }
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium border ${style.bg} ${style.text} ${style.border} ${className}`}
      title={`Verification Status: ${style.label}`}
    >
      {showIcon && renderIcon()}
      {style.label}
    </span>
  );
};

interface PriorityBadgeProps {
  priority: PriorityLevel;
  className?: string;
}

export const PriorityBadge: React.FC<PriorityBadgeProps> = ({ priority, className = '' }) => {
  const style = getPriorityBadgeStyle(priority);
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium uppercase tracking-wider border ${style.bg} ${style.text} ${style.border} ${className}`}
    >
      {priority}
    </span>
  );
};

interface TagProps {
  label: string;
  className?: string;
}

export const Tag: React.FC<TagProps> = ({ label, className = '' }) => (
  <span className={`inline-flex items-center px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-xs font-mono border border-slate-200 ${className}`}>
    {label}
  </span>
);
