/**
 * RelayPoint Centralized API Client.
 * Handles timeouts, network failure translation, and typed responses.
 */

import {
  ActivityItem,
  ConnectRepositoryPayload,
  HealthStatus,
  IngestionResult,
  ReportDetail,
  ReportSummary,
  Repository,
  SourceChunk,
  SourceChunksResponse,
} from '../types/api';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

export class ApiError extends Error {
  status: number;
  detail: string;

  constructor(status: number, detail: string) {
    super(detail || `API Request failed with status ${status}`);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

async function fetchWithTimeout(url: string, options: RequestInit = {}, timeoutMs = 25000): Promise<Response> {
  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs);

  try {
    const response = await fetch(url, {
      ...options,
      signal: controller.signal,
    });
    return response;
  } catch (error: any) {
    if (error.name === 'AbortError') {
      throw new ApiError(408, `Request timed out after ${timeoutMs / 1000}s`);
    }
    throw new ApiError(0, error.message || 'Network connection to backend failed.');
  } finally {
    clearTimeout(timeoutId);
  }
}

async function request<T>(endpoint: string, options: RequestInit = {}, timeoutMs = 25000): Promise<T> {
  const url = `${API_BASE_URL.replace(/\/$/, '')}/${endpoint.replace(/^\//, '')}`;
  const headers = {
    'Accept': 'application/json',
    'Content-Type': 'application/json',
    ...(options.headers || {}),
  };

  const response = await fetchWithTimeout(url, { ...options, headers }, timeoutMs);

  if (!response.ok) {
    let detail = `HTTP Error ${response.status}`;
    try {
      const errData = await response.json();
      detail = errData.detail || detail;
    } catch {
      detail = await response.text() || detail;
    }
    throw new ApiError(response.status, detail);
  }

  return response.json() as Promise<T>;
}

export const api = {
  // System Health
  checkHealth: () => request<HealthStatus>('/health'),

  // Repositories
  listRepositories: () => request<Repository[]>('/repositories'),
  
  getRepository: (repoId: string) => request<Repository>(`/repositories/${encodeURIComponent(repoId)}`),
  
  connectRepository: (payload: ConnectRepositoryPayload) =>
    request<Repository>('/repositories/connect', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  ingestRepository: (repoId: string) =>
    request<IngestionResult>(`/repositories/${encodeURIComponent(repoId)}/ingest`, {
      method: 'POST',
    }, 45000), // Longer timeout for Git ingestion

  getRepositorySources: (repoId: string, params: { sourceType?: string; limit?: number; offset?: number } = {}) => {
    const query = new URLSearchParams();
    if (params.sourceType) query.set('source_type', params.sourceType);
    if (params.limit) query.set('limit', String(params.limit));
    if (params.offset) query.set('offset', String(params.offset));
    const qs = query.toString() ? `?${query.toString()}` : '';
    return request<SourceChunksResponse>(`/repositories/${encodeURIComponent(repoId)}/sources${qs}`);
  },

  getSourceChunk: (repoId: string, chunkId: string) =>
    request<SourceChunk>(`/repositories/${encodeURIComponent(repoId)}/sources/${encodeURIComponent(chunkId)}`),

  getRepositoryActivity: (repoId: string, limit = 50) =>
    request<ActivityItem[]>(`/repositories/${encodeURIComponent(repoId)}/activity?limit=${limit}`),

  // Analysis & Reports
  analyzeRepository: (repoId: string) =>
    request<{ report_id: string; title: string; verification_stats: Record<string, number> }>(
      `/repositories/${encodeURIComponent(repoId)}/analyze`,
      { method: 'POST' },
      60000 // Extended timeout for AI synthesis
    ),

  listRepositoryReports: (repoId: string) =>
    request<ReportSummary[]>(`/repositories/${encodeURIComponent(repoId)}/reports`),

  getReport: (reportId: string) =>
    request<ReportDetail>(`/reports/${encodeURIComponent(reportId)}`),

  verifyReport: (reportId: string) =>
    request<{ report_id: string; status: string; verification_stats: Record<string, number> }>(
      `/reports/${encodeURIComponent(reportId)}/verify`,
      { method: 'POST' }
    ),
};
