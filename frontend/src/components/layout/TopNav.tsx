import React from 'react';
import { RefreshCw, Activity } from 'lucide-react';
import { Button } from '../ui/Button';

interface TopNavProps {
  title: string;
  subtitle?: string;
  backendHealthy: boolean;
  onRefresh?: () => void;
  isRefreshing?: boolean;
}

export const TopNav: React.FC<TopNavProps> = ({
  title,
  subtitle,
  backendHealthy,
  onRefresh,
  isRefreshing = false,
}) => {
  return (
    <header className="h-16 bg-white border-b border-slate-200 px-8 flex items-center justify-between shrink-0 shadow-sm/50">
      <div>
        <h1 className="text-lg font-semibold text-slate-900 tracking-tight">{title}</h1>
        {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
      </div>

      <div className="flex items-center gap-3">
        {/* Health status badge */}
        <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-50 border border-slate-200 text-xs">
          <Activity className={`w-3.5 h-3.5 ${backendHealthy ? 'text-emerald-500' : 'text-rose-500'}`} />
          <span className="text-slate-600 font-medium">
            API {backendHealthy ? 'Connected' : 'Offline'}
          </span>
        </div>

        {/* Global Refresh Button */}
        {onRefresh && (
          <Button
            variant="outline"
            size="sm"
            onClick={onRefresh}
            isLoading={isRefreshing}
            icon={<RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? 'animate-spin' : ''}`} />}
          >
            Refresh
          </Button>
        )}
      </div>
    </header>
  );
};
