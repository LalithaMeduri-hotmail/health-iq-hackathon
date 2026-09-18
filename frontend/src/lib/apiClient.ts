/**
 * The single typed HTTP client (frontend.instructions.md). Components/hooks never call
 * `fetch`/`axios` directly - always go through this module.
 */

import { getAccessToken, isDemoIdentityAllowed } from './auth';
import type { ApiResponse, ProblemDetails } from './types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

/**
 * Called when the backend rejects a request the caller believed was authenticated - i.e. the
 * session cookie expired or its signing key changed. `AuthContext` registers the handler that
 * drops cached data and sends the user back to sign in.
 */
type UnauthorizedHandler = () => void;
let unauthorizedHandler: UnauthorizedHandler | null = null;

export function setUnauthorizedHandler(handler: UnauthorizedHandler | null): void {
  unauthorizedHandler = handler;
}

// `/auth/me` answers 401 for an ordinary signed-out visitor and `/auth/login` for a wrong PIN.
// Neither is an expired session, and treating them as one would bounce the user off the very page
// they need.
function isExpectedUnauthorized(path: string): boolean {
  return path.startsWith('/api/v1/auth/');
}

export function absoluteApiUrl(path: string): string {
  return `${API_BASE_URL}${path}`;
}

export class ApiError extends Error {
  constructor(public problem: ProblemDetails) {
    super(problem.title);
  }
}

interface RequestOptions {
  /**
   * Treat a 401 as an ordinary outcome instead of a dead session. Bootstrap calls that run on
   * every page need this: otherwise a stale cookie bounces the visitor to "session expired" from
   * pages that do not require a session at all, such as sign-up.
   */
  allowUnauthorized?: boolean;
}

async function request<TData>(
  path: string,
  init?: RequestInit,
  options?: RequestOptions,
): Promise<ApiResponse<TData>> {
  const headers = new Headers(init?.headers);
  headers.set('Accept', 'application/json');

  const token = await getAccessToken();
  if (token) {
    headers.set('Authorization', `Bearer ${token}`);
  } else if (isDemoIdentityAllowed()) {
    headers.set('X-Demo-User-Id', 'demo-user');
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers, credentials: 'include' });

  if (!response.ok) {
    if (response.status === 401 && !isExpectedUnauthorized(path) && !options?.allowUnauthorized) {
      unauthorizedHandler?.();
    }
    const problem = (await response.json()) as ProblemDetails;
    throw new ApiError(problem);
  }

  return (await response.json()) as ApiResponse<TData>;
}

export const apiClient = {
  get: <TData>(path: string, options?: RequestOptions) =>
    request<TData>(path, { method: 'GET' }, options),
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
