import React from 'react';
import { Sidebar, NavigationTab } from './Sidebar';
import { TopNav } from './TopNav';

interface AppLayoutProps {
  currentTab: NavigationTab;
  onSelectTab: (tab: NavigationTab) => void;
  title: string;
  subtitle?: string;
  backendHealthy: boolean;
  onRefresh?: () => void;
  isRefreshing?: boolean;
  children: React.ReactNode;
}

export const AppLayout: React.FC<AppLayoutProps> = ({
  currentTab,
  onSelectTab,
  title,
  subtitle,
  backendHealthy,
  onRefresh,
  isRefreshing,
  children,
}) => {
  return (
    <div className="flex h-screen w-screen overflow-hidden bg-slate-50">
      <Sidebar currentTab={currentTab} onSelectTab={onSelectTab} backendHealthy={backendHealthy} />

      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        <TopNav
          title={title}
          subtitle={subtitle}
          backendHealthy={backendHealthy}
          onRefresh={onRefresh}
          isRefreshing={isRefreshing}
        />

        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-7xl mx-auto space-y-6">
            {children}
          </div>
        </main>
      </div>
    </div>
  );
};
