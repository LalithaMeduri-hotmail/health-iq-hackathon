/**
 * Account module API calls (frontend.instructions.md - the ONLY place this feature touches
 * `apiClient`). The session itself is an HttpOnly cookie set by the backend; nothing here ever
 * stores a token in JS-accessible storage.
 */

import { apiClient } from '@/lib/apiClient';
import type { ApiResponse } from '@/lib/types';

import type { AccountPublic, AuthResult, LoginInput, RegisterInput } from './types';

export async function registerAccount(input: RegisterInput): Promise<ApiResponse<AuthResult>> {
  return apiClient.post<AuthResult>('/api/v1/auth/register', input);
}

export async function loginAccount(input: LoginInput): Promise<ApiResponse<AuthResult>> {
  return apiClient.post<AuthResult>('/api/v1/auth/login', input);
}

export async function logoutAccount(): Promise<ApiResponse<{ loggedOut: boolean }>> {
  return apiClient.post<{ loggedOut: boolean }>('/api/v1/auth/logout');
}

export async function fetchCurrentAccount(): Promise<ApiResponse<AccountPublic>> {
  return apiClient.get<AccountPublic>('/api/v1/auth/me');
}
