/**
 * Health Profile feature API calls (frontend.instructions.md - the ONLY place this feature
 * touches `apiClient`; components/hooks call these functions, never `fetch` directly).
 */

import { ApiError, apiClient } from '@/lib/apiClient';
import type { ApiResponse } from '@/lib/types';

import type {
  PreferencesUpdate,
  Profile,
  ProfileResponse,
  ReportAnalyzeResponse,
  ReportDetailResponse,
  SpecialistGuidance,
} from './types';

export async function fetchProfile(): Promise<ApiResponse<ProfileResponse>> {
  return apiClient.get<ProfileResponse>('/api/v1/profile');
}

export async function fetchReportDetail(reportId: string): Promise<ApiResponse<ReportDetailResponse>> {
  return apiClient.get<ReportDetailResponse>(`/api/v1/reports/${encodeURIComponent(reportId)}`);
}

export async function updatePreferences(body: PreferencesUpdate): Promise<ApiResponse<Profile>> {
  return apiClient.put<Profile>('/api/v1/profile/preferences', body);
}

export async function suggestSpecialists(reportId: string): Promise<ApiResponse<SpecialistGuidance>> {
  return apiClient.post<SpecialistGuidance>('/api/v1/specialists/suggest', { reportId });
}

export async function analyzeReport(file: File): Promise<ApiResponse<ReportAnalyzeResponse>> {
  const form = new FormData();
  form.set('consent', 'true');
  form.set('file', file);
  return apiClient.post<ReportAnalyzeResponse>('/api/v1/reports/analyze', form);
}

export { ApiError };
