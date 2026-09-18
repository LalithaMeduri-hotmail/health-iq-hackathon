/**
 * Report Comparison feature API calls (frontend.instructions.md - the ONLY place this feature
 * touches `apiClient`; components/hooks call these functions, never `fetch` directly).
 */

import { ApiError, apiClient } from '@/lib/apiClient';
import type { ApiResponse } from '@/lib/types';

import type {
  ComparisonResult,
  ReportAnalyzeResponse,
  ReportListResponse,
} from './types';

export async function fetchReports(profileId?: string | null): Promise<ApiResponse<ReportListResponse>> {
  const query = profileId ? `?profileId=${encodeURIComponent(profileId)}` : '';
  return apiClient.get<ReportListResponse>(`/api/v1/reports${query}`);
}

export async function analyzeReport(
  file: File,
  profileId?: string | null,
): Promise<ApiResponse<ReportAnalyzeResponse>> {
  const form = new FormData();
  form.set('consent', 'true');
  form.set('file', file);
  if (profileId) {
    form.set('profileId', profileId);
  }
  return apiClient.post<ReportAnalyzeResponse>('/api/v1/reports/analyze', form);
}

export async function compareReports(
  oldReportId: string,
  currentReportId: string,
  profileId?: string | null,
): Promise<ApiResponse<ComparisonResult>> {
  return apiClient.post<ComparisonResult>('/api/v1/reports/compare', {
    oldReportId,
    currentReportId,
    ...(profileId ? { profileId } : {}),
  });
}

export { ApiError };
