import React, { useEffect, useState } from 'react';
import { api } from './services/api';
import { ActivityItem, ReportSummary, Repository } from './types/api';
import { AppLayout } from './components/layout/AppLayout';
import { NavigationTab } from './components/layout/Sidebar';
import { DashboardPage } from './pages/DashboardPage';
import { RepositoriesPage } from './pages/RepositoriesPage';
import { RepositoryDetailPage } from './pages/RepositoryDetailPage';
import { ReportsListPage } from './pages/ReportsListPage';
import { ReportDetailPage } from './pages/ReportDetailPage';

export const App: React.FC = () => {
  const [currentTab, setCurrentTab] = useState<NavigationTab>('dashboard');
  const [selectedRepoId, setSelectedRepoId] = useState<string | null>(null);
  const [selectedReportId, setSelectedReportId] = useState<string | null>(null);

  // Global State
  const [repositories, setRepositories] = useState<Repository[]>([]);
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [recentActivity, setRecentActivity] = useState<ActivityItem[]>([]);
  const [backendHealthy, setBackendHealthy] = useState<boolean>(true);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  // Ingestion & Analysis Action States
  const [ingestingRepoId, setIngestingRepoId] = useState<string | null>(null);
  const [analyzingRepoId, setAnalyzingRepoId] = useState<string | null>(null);

  const loadGlobalData = async () => {
    setIsRefreshing(true);
    try {
      // 1. Health check
      try {
        const health = await api.checkHealth();
        setBackendHealthy(health.status === 'healthy' && health.database === 'connected');
      } catch {
        setBackendHealthy(false);
      }

      // 2. Fetch repositories
      const repos = await api.listRepositories();
      setRepositories(repos);

      // 3. Fetch reports across all repositories
      const allReports: ReportSummary[] = [];
      const allActivity: ActivityItem[] = [];

      for (const r of repos) {
        try {
          const rReports = await api.listRepositoryReports(r.id);
          allReports.push(...rReports);

          const rActivity = await api.getRepositoryActivity(r.id, 10);
          allActivity.push(...rActivity);
        } catch (err) {
          console.warn(`Could not fetch details for repo ${r.id}`, err);
        }
      }

      // Sort reports by created_at descending
      allReports.sort((a, b) => b.created_at.localeCompare(a.created_at));
      setReports(allReports);

      // Sort activity by timestamp descending
      allActivity.sort((a, b) => (b.timestamp || '').localeCompare(a.timestamp || ''));
      setRecentActivity(allActivity);
    } catch (err) {
      console.error('Failed to load global workspace data', err);
    } finally {
      setIsRefreshing(false);
    }
  };

  useEffect(() => {
    loadGlobalData();
    const interval = setInterval(() => {
      api.checkHealth().then((h) => setBackendHealthy(h.status === 'healthy')).catch(() => setBackendHealthy(false));
    }, 15000);
    return () => clearInterval(interval);
  }, []);

  const handleSelectTab = (tab: NavigationTab) => {
    setCurrentTab(tab);
    setSelectedRepoId(null);
    setSelectedReportId(null);
  };

  const handleSelectRepository = (repoId: string) => {
    setSelectedRepoId(repoId);
    setSelectedReportId(null);
  };

  const handleOpenReport = (reportId: string) => {
    setSelectedReportId(reportId);
  };

  const handleIngestRepo = async (repoId: string) => {
    setIngestingRepoId(repoId);
    try {
      const res = await api.ingestRepository(repoId);
      alert(`Ingestion complete! Ingested ${res.chunks_created} source chunks (${res.duplicates_skipped} duplicates skipped).`);
      loadGlobalData();
    } catch (err: any) {
      alert(`Ingestion failed: ${err.detail || err.message}`);
    } finally {
      setIngestingRepoId(null);
    }
  };

  const handleAnalyzeRepo = async (repoId: string) => {
    setAnalyzingRepoId(repoId);
    try {
      const res = await api.analyzeRepository(repoId);
      loadGlobalData();
      setSelectedReportId(res.report_id);
    } catch (err: any) {
      alert(`AI Synthesis failed: ${err.detail || err.message}`);
    } finally {
      setAnalyzingRepoId(null);
    }
  };

  // Compute Layout Titles and Content
  let pageTitle = 'RelayPoint Dashboard';
  let pageSubtitle = 'Automated Knowledge Handover Platform';

  if (selectedReportId) {
    pageTitle = 'Handover Report';
    pageSubtitle = 'Evidence-grounded project analysis';
  } else if (selectedRepoId) {
    const currentRepo = repositories.find((r) => r.id === selectedRepoId);
    pageTitle = currentRepo ? currentRepo.full_name : 'Repository Detail';
    pageSubtitle = 'Repository history, activity, and analysis control';
  } else if (currentTab === 'repositories') {
    pageTitle = 'Repositories';
    pageSubtitle = 'Tracked Git and GitHub repositories';
  } else if (currentTab === 'reports') {
    pageTitle = 'Handover Reports';
    pageSubtitle = 'Synthesized knowledge handovers and evidence metrics';
  }

  const renderContent = () => {
    if (selectedReportId) {
      return (
        <ReportDetailPage
          reportId={selectedReportId}
          onBack={() => setSelectedReportId(null)}
          onSelectRepository={handleSelectRepository}
        />
      );
    }

    if (selectedRepoId) {
      return (
        <RepositoryDetailPage
          repositoryId={selectedRepoId}
          onBack={() => setSelectedRepoId(null)}
          onOpenReport={handleOpenReport}
        />
      );
    }

    switch (currentTab) {
      case 'repositories':
        return (
          <RepositoriesPage
            repositories={repositories}
            onSelectRepository={handleSelectRepository}
            onRefresh={loadGlobalData}
            onRepositoryConnected={(newRepo) => {
              setRepositories((prev) => [newRepo, ...prev]);
            }}
            onIngestRepo={handleIngestRepo}
            onAnalyzeRepo={handleAnalyzeRepo}
            ingestingRepoId={ingestingRepoId}
            analyzingRepoId={analyzingRepoId}
          />
        );
      case 'reports':
        return (
          <ReportsListPage
            reports={reports}
            repositories={repositories}
            onOpenReport={handleOpenReport}
            onSelectRepository={handleSelectRepository}
          />
        );
      case 'dashboard':
      default:
        return (
          <DashboardPage
            repositories={repositories}
            reports={reports}
            recentActivity={recentActivity}
            onSelectRepository={handleSelectRepository}
            onOpenReport={handleOpenReport}
            onRefresh={loadGlobalData}
            onRepositoryConnected={(newRepo) => {
              setRepositories((prev) => [newRepo, ...prev]);
            }}
            onIngestRepo={handleIngestRepo}
            onAnalyzeRepo={handleAnalyzeRepo}
            ingestingRepoId={ingestingRepoId}
            analyzingRepoId={analyzingRepoId}
          />
        );
    }
  };

  return (
    <AppLayout
      currentTab={currentTab}
      onSelectTab={handleSelectTab}
      title={pageTitle}
      subtitle={pageSubtitle}
      backendHealthy={backendHealthy}
      onRefresh={loadGlobalData}
      isRefreshing={isRefreshing}
    >
      {renderContent()}
    </AppLayout>
  );
};
