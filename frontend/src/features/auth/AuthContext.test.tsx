/**
 * Session lifecycle tests: signing out must actually sign you out, and a session that dies
 * mid-use must send the user back to sign in rather than leaving a dead error on the page.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ApiError, apiClient, setUnauthorizedHandler } from '@/lib/apiClient';

import { AuthProvider, useAuth } from './AuthContext';
import type { AccountPublic } from './types';

vi.mock('./api', async () => {
  const actual = await vi.importActual<typeof import('./api')>('./api');
  return {
    ...actual,
    fetchCurrentAccount: vi.fn(),
    loginAccount: vi.fn(),
    registerAccount: vi.fn(),
    logoutAccount: vi.fn(),
  };
});

const api = await import('./api');

const ACCOUNT: AccountPublic = {
  userId: 'user-1',
  username: 'demo_user',
  displayName: 'Demo User',
  mobile: null,
  email: null,
};

function envelope<T>(data: T) {
  return {
    requestId: 'req-1',
    generatedAt: '2026-09-17T00:00:00Z',
    apiVersion: 'v1',
    disclaimer: 'demo disclaimer',
    safety: { pass: true, notes: [], reviewerVersion: 'safety-1.0.0' },
    data,
  };
}

function unauthorized() {
  return new ApiError({
    type: 'https://healthiq/errors/unauthenticated',
    title: 'Unauthenticated',
    status: 401,
    detail: 'Session expired or invalid; please sign in again',
    instance: 'req-1',
    errors: [],
  });
}

/** Shows who the app thinks is signed in, plus where the router currently is. */
function Probe() {
  const { account, logout } = useAuth();
  const location = useLocation();
  return (
    <div>
      <span data-testid="account">{account?.displayName ?? 'signed-out'}</span>
      <span data-testid="path">{`${location.pathname}${location.search}`}</span>
      <button type="button" onClick={() => void logout()}>
        Sign out
      </button>
    </div>
  );
}

function renderAuth(queryClient: QueryClient) {
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={['/profile']}>
        <AuthProvider>
          <Routes>
            <Route path="/profile" element={<Probe />} />
            <Route path="/login" element={<Probe />} />
          </Routes>
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe('session lifecycle', () => {
  let queryClient: QueryClient;

  beforeEach(() => {
    vi.restoreAllMocks();
    setUnauthorizedHandler(null);
    queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    vi.mocked(api.fetchCurrentAccount).mockResolvedValue(envelope(ACCOUNT));
    vi.mocked(api.logoutAccount).mockResolvedValue(envelope({ loggedOut: true }));
  });

  it('clears the signed-in account when the user signs out', async () => {
    const user = userEvent.setup();
    renderAuth(queryClient);

    expect(await screen.findByText('Demo User')).toBeInTheDocument();

    // `/auth/me` keeps answering; only clearing the cache can sign the user out in the UI.
    await user.click(screen.getByRole('button', { name: 'Sign out' }));

    await waitFor(() => expect(screen.getByTestId('account')).toHaveTextContent('signed-out'));
    expect(api.logoutAccount).toHaveBeenCalled();
  });

  it('sends the user to the login page after signing out', async () => {
    const user = userEvent.setup();
    renderAuth(queryClient);

    await screen.findByText('Demo User');
    await user.click(screen.getByRole('button', { name: 'Sign out' }));

    await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/login'));
  });

  it('drops every cached query so the next person sees none of this one data', async () => {
    const user = userEvent.setup();
    renderAuth(queryClient);
    queryClient.setQueryData(['profile', null], envelope({ secret: 'previous user report' }));

    await screen.findByText('Demo User');
    await user.click(screen.getByRole('button', { name: 'Sign out' }));

    await waitFor(() => expect(queryClient.getQueryData(['profile', null])).toBeUndefined());
  });

  it('signs the user out locally even when the logout request fails', async () => {
    const user = userEvent.setup();
    vi.mocked(api.logoutAccount).mockRejectedValue(unauthorized());
    renderAuth(queryClient);

    await screen.findByText('Demo User');
    await user.click(screen.getByRole('button', { name: 'Sign out' }));

    await waitFor(() => expect(screen.getByTestId('account')).toHaveTextContent('signed-out'));
    expect(screen.getByTestId('path')).toHaveTextContent('/login');
  });

  it('asks the user to sign in again when a request finds the session expired', async () => {
    renderAuth(queryClient);
    await screen.findByText('Demo User');

    // A real request through the client, answered 401 the way an expired cookie would be.
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(unauthorized().problem), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    await expect(apiClient.get('/api/v1/profile')).rejects.toBeInstanceOf(ApiError);

    await waitFor(() => expect(screen.getByTestId('path')).toHaveTextContent('/login?reason=expired'));
    expect(screen.getByTestId('account')).toHaveTextContent('signed-out');
  });

  it('does not bounce a signed-out visitor off the login page', async () => {
    renderAuth(queryClient);
    await screen.findByText('Demo User');

    vi.spyOn(globalThis, 'fetch').mockResolvedValue(
      new Response(JSON.stringify(unauthorized().problem), {
        status: 401,
        headers: { 'Content-Type': 'application/json' },
      }),
    );
    // `/auth/me` and a wrong PIN both answer 401 without the session having expired.
    await expect(apiClient.get('/api/v1/auth/me')).rejects.toBeInstanceOf(ApiError);

    expect(screen.getByTestId('path')).toHaveTextContent('/profile');
  });
});
