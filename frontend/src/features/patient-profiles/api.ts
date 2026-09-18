/**
 * Patient-profile API calls (frontend.instructions.md - the ONLY place this feature touches
 * `apiClient`). Every path carries the `profileId` explicitly so a request can never be
 * implicitly scoped to whichever profile happened to be active when the module loaded.
 */

import { ApiError, apiClient } from '@/lib/apiClient';
import type { ApiResponse } from '@/lib/types';

import type {
  PatientProfile,
  PatientProfileCreateInput,
  PatientProfileInput,
  PatientProfileListResponse,
} from './types';

const BASE = '/api/v1/profiles';

function profilePath(profileId: string, suffix = ''): string {
  return `${BASE}/${encodeURIComponent(profileId)}${suffix}`;
}

export function fetchPatientProfiles(): Promise<ApiResponse<PatientProfileListResponse>> {
  // Runs on every page as a bootstrap, so a 401 here means "nobody is signed in yet", not "the
  // session just died" - letting it trip the global handler would block the sign-up page.
  return apiClient.get<PatientProfileListResponse>(BASE, { allowUnauthorized: true });
}

export function createPatientProfile(
  input: PatientProfileCreateInput,
): Promise<ApiResponse<PatientProfile>> {
  return apiClient.post<PatientProfile>(BASE, input);
}

export function updatePatientProfile(
  profileId: string,
  input: PatientProfileInput & { etag?: string | null },
): Promise<ApiResponse<PatientProfile>> {
  return apiClient.put<PatientProfile>(profilePath(profileId), input);
}

export function archivePatientProfile(profileId: string): Promise<ApiResponse<PatientProfile>> {
  return apiClient.post<PatientProfile>(profilePath(profileId, '/archive'));
}

export function restorePatientProfile(profileId: string): Promise<ApiResponse<PatientProfile>> {
  return apiClient.post<PatientProfile>(profilePath(profileId, '/restore'));
}

export function withdrawConsent(profileId: string): Promise<ApiResponse<PatientProfile>> {
  return apiClient.post<PatientProfile>(profilePath(profileId, '/consent/withdraw'));
}

export function grantConsent(profileId: string): Promise<ApiResponse<PatientProfile>> {
  return apiClient.post<PatientProfile>(profilePath(profileId, '/consent/grant'));
}

export function activateProfile(profileId: string): Promise<ApiResponse<PatientProfile>> {
  return apiClient.post<PatientProfile>(profilePath(profileId, '/activate'));
}

export { ApiError };