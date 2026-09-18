import { render, screen } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { useAuth } from './AuthContext';
import { GuestOnly, RequireAuth } from './AuthRoute';

vi.mock('./AuthContext', () => ({ useAuth: vi.fn() }));

const ACCOUNT = {
  userId: 'user-1',
  username: 'demo_user',
  displayName: 'Demo User',
  mobile: null,
  email: null,
};

function renderRoutes(initialPath: string) {
  return render(
    <MemoryRouter initialEntries={[initialPath]}>
      <Routes>
        <Route
          path="/"
          element={<h1>Dashboard</h1>}
        />
        <Route
          path="/profile"
          element={
            <RequireAuth>
              <h1>Health Profile</h1>
            </RequireAuth>
          }
        />
        <Route
          path="/login"
          element={
            <GuestOnly>
              <h1>Sign in</h1>
            </GuestOnly>
          }
        />
      </Routes>
    </MemoryRouter>,
  );
}

describe('authentication routes', () => {
  beforeEach(() => {
    vi.mocked(useAuth).mockReturnValue({
      account: null,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });
  });

  it('keeps the landing page public for a signed-out visitor', () => {
    renderRoutes('/');

    expect(screen.getByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
  });

  it('sends a signed-out visitor from a feature to sign in', async () => {
    renderRoutes('/profile');

    expect(await screen.findByRole('heading', { name: 'Sign in' })).toBeInTheDocument();
  });

  it('shows a protected feature to a signed-in visitor', () => {
    vi.mocked(useAuth).mockReturnValue({
      account: ACCOUNT,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    renderRoutes('/profile');

    expect(screen.getByRole('heading', { name: 'Health Profile' })).toBeInTheDocument();
  });

  it('returns a signed-in visitor from the login page to the dashboard', async () => {
    vi.mocked(useAuth).mockReturnValue({
      account: ACCOUNT,
      isLoading: false,
      login: vi.fn(),
      register: vi.fn(),
      logout: vi.fn(),
    });

    renderRoutes('/login');

    expect(await screen.findByRole('heading', { name: 'Dashboard' })).toBeInTheDocument();
  });
});