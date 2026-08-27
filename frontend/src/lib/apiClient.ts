/**
 * The single typed HTTP client (frontend.instructions.md). Components/hooks never call
 * `fetch`/`axios` directly - always go through this module.
 */

import { getAccessToken, isDemoMode } from './auth';
import type { ApiResponse, ProblemDetails } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

export class ApiError extends Error {
  constructor(public problem: ProblemDetails) {
    super(problem.title);
  }
}

async function request<TData>(path: string, init?: RequestInit): Promise<ApiResponse<TData>> {
  const headers = new Headers(init?.headers);
  headers.set('Accept', 'application/json');

  const token = await getAccessToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  } else if (isDemoMode) {
    headers.set('X-Demo-User-Id', 'demo-user');
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });

  if (!response.ok) {
    const problem = (await response.json()) as ProblemDetails;
    throw new ApiError(problem);
  }

  return (await response.json()) as ApiResponse<TData>;
}

export const apiClient = {
  get: <TData>(path: string) => request<TData>(path, { method: 'GET' }),
  post: <TData>(path: string, body?: unknown) =>
    request<TData>(path, {
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body),
      headers: body instanceof FormData ? undefined : { 'Content-Type': 'application/json' },
    }),
  put: <TData>(path: string, body?: unknown) =>
    request<TData>(path, {
      method: 'PUT',
      body: JSON.stringify(body),
      headers: { 'Content-Type': 'application/json' },
    }),
};
