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

function scoped(path: string, profileId?: string | null): string {
  return profileId ? `${path}${path.includes('?') ? '&' : '?'}profileId=${encodeURIComponent(profileId)}` : path;
}

export async function fetchProfile(profileId?: string | null): Promise<ApiResponse<ProfileResponse>> {
  try {
    return await apiClient.get<ProfileResponse>(scoped('/api/v1/profile', profileId));
  } catch (error) {
    // A stored profile id can outlive the profile itself; fall back to the account's own page
    // rather than leaving the user on a dead error.
    if (profileId && error instanceof ApiError && error.problem.status === 404) {
      return apiClient.get<ProfileResponse>('/api/v1/profile');
    }
    throw error;
  }
}

export async function fetchReportDetail(
  reportId: string,
  profileId?: string | null,
): Promise<ApiResponse<ReportDetailResponse>> {
  return apiClient.get<ReportDetailResponse>(
    scoped(`/api/v1/reports/${encodeURIComponent(reportId)}`, profileId),
  );
}

export async function updatePreferences(body: PreferencesUpdate): Promise<ApiResponse<Profile>> {
  return apiClient.put<Profile>('/api/v1/profile/preferences', body);
}

export async function suggestSpecialists(reportId: string): Promise<ApiResponse<SpecialistGuidance>> {
  return apiClient.post<SpecialistGuidance>('/api/v1/specialists/suggest', { reportId });
}

export async function analyzeReport(
  file: File,
  profileId?: string,
): Promise<ApiResponse<ReportAnalyzeResponse>> {
  const form = new FormData();
  form.set('consent', 'true');
  form.set('file', file);
  if (profileId) {
    form.set('profileId', profileId);
  }
  return apiClient.post<ReportAnalyzeResponse>('/api/v1/reports/analyze', form);
}

export { ApiError };
