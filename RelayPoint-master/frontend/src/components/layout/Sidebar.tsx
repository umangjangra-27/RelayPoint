import React from 'react';
import {
  LayoutDashboard,
  GitBranch,
  FileText,
  ShieldCheck,
  Server,
  Layers,
} from 'lucide-react';

export type NavigationTab = 'dashboard' | 'repositories' | 'reports';

interface SidebarProps {
  currentTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  backendHealthy: boolean;
}

export const Sidebar: React.FC<SidebarProps> = ({ currentTab, onSelectTab, backendHealthy }) => {
  const navItems = [
    { id: 'dashboard' as NavigationTab, label: 'Dashboard', icon: LayoutDashboard },
    { id: 'repositories' as NavigationTab, label: 'Repositories', icon: GitBranch },
    { id: 'reports' as NavigationTab, label: 'Handover Reports', icon: FileText },
  ];

  return (
    <aside className="w-64 bg-slate-900 text-slate-300 flex flex-col shrink-0 border-r border-slate-800">
      {/* Brand Header */}
      <div className="h-16 px-6 flex items-center gap-3 border-b border-slate-800/80 bg-slate-950/40">
        <div className="w-8 h-8 rounded-lg bg-brand-600 flex items-center justify-center text-white shadow-md shadow-brand-500/20">
          <Layers className="w-5 h-5" />
        </div>
        <div>
          <span className="text-base font-bold text-white tracking-tight">RelayPoint</span>
          <span className="block text-[10px] text-slate-400 font-medium tracking-wide uppercase">Handover Platform</span>
        </div>
      </div>

      {/* Primary Navigation */}
      <div className="flex-1 px-3 py-6 space-y-1">
        <div className="px-3 pb-2 text-[11px] font-semibold text-slate-400 uppercase tracking-wider">
          Workspace
        </div>
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = currentTab === item.id;
          return (
            <button
              key={item.id}
              onClick={() => onSelectTab(item.id)}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-md text-sm font-medium transition-all ${
                isActive
                  ? 'bg-brand-600 text-white shadow-sm'
                  : 'text-slate-400 hover:text-white hover:bg-slate-800/60'
              }`}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span>{item.label}</span>
            </button>
          );
        })}
      </div>

      {/* Footer System Status */}
      <div className="p-4 border-t border-slate-800 bg-slate-950/30">
        <div className="flex items-center justify-between text-xs mb-2">
          <span className="text-slate-400 flex items-center gap-1.5">
            <Server className="w-3.5 h-3.5" /> Backend
          </span>
          <span className={`inline-flex items-center gap-1 text-[11px] font-medium ${backendHealthy ? 'text-emerald-400' : 'text-rose-400'}`}>
            <span className={`w-1.5 h-1.5 rounded-full ${backendHealthy ? 'bg-emerald-400' : 'bg-rose-400'} animate-pulse`} />
            {backendHealthy ? 'Online' : 'Disconnected'}
          </span>
        </div>
        <div className="flex items-center justify-between text-[11px] text-slate-500">
          <span className="flex items-center gap-1">
            <ShieldCheck className="w-3 h-3 text-slate-400" /> Evidence Engine
          </span>
          <span className="font-mono text-[10px] text-slate-400">SQLite + WAL</span>
        </div>
      </div>
    </aside>
  );
};
