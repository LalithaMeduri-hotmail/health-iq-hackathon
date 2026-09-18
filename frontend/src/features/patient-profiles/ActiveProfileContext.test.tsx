/**
 * Profile switching must be a hard boundary: the previous person's cached medical data has to be
 * gone before the next profile renders, and the switch has to be reported to the server so it is
 * auditable.
 */

import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { beforeEach, describe, expect, it, vi } from 'vitest';

import { ActiveProfileProvider, useActiveProfile } from './ActiveProfileContext';
import { activateProfile, fetchPatientProfiles } from './api';

vi.mock('./api', () => ({
  fetchPatientProfiles: vi.fn(),
  activateProfile: vi.fn().mockResolvedValue({ data: {} }),
}));

// The provider only queries once a caller is identified; these tests are about the signed-in path.
vi.mock('@/features/auth', () => ({
  useAuth: () => ({ account: { userId: 'acct-1', username: 'asha' }, isLoading: false }),
}));

function profile(id: string, displayName: string, isOwner = false) {
  return {
    id,
    accountId: 'acct-1',
    displayName,
    relationshipToAccountOwner: isOwner ? 'self' : 'child',
    dateOfBirth: null,
    sex: null,
    preferredLanguage: 'en',
    country: null,
    city: null,
    dietaryPreference: null,
    allergies: [],
    foodIntolerances: [],
    dislikedFoods: [],
    knownConditions: [],
    healthGoals: [],
    isAccountOwnerProfile: isOwner,
    status: 'active' as const,
    consentStatus: 'granted' as const,
    consentVersion: '1.0',
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    etag: null,
  };
}

function Consumer() {
  const { activeProfile, profiles, setActiveProfile } = useActiveProfile();
  return (
    <div>
      <p data-testid="active">{activeProfile?.displayName ?? 'none'}</p>
      {profiles.map((item) => (
        <button key={item.id} type="button" onClick={() => setActiveProfile(item.id)}>
          {`switch-${item.displayName}`}
        </button>
      ))}
    </div>
  );
}

function renderProvider(queryClient: QueryClient) {
  return render(
    <QueryClientProvider client={queryClient}>
      <ActiveProfileProvider>
        <Consumer />
      </ActiveProfileProvider>
    </QueryClientProvider>,
  );
}

describe('ActiveProfileContext', () => {
  beforeEach(() => {
    window.localStorage.clear();
    vi.mocked(fetchPatientProfiles).mockResolvedValue({
      requestId: 'req-1',
      generatedAt: '2026-01-01T00:00:00Z',
      apiVersion: 'v1',
      disclaimer: '',
      safety: { pass: true, notes: [], reviewerVersion: 'safety-1.0.0' },
      data: {
        profiles: [profile('pp-owner', 'Asha Ramanathan', true), profile('pp-child', 'Ravi Junior')],
        activeProfileId: 'pp-owner',
      },
    } as never);
  });

  it('defaults to the account owner profile', async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderProvider(queryClient);

    await waitFor(() =>
      expect(screen.getByTestId('active')).toHaveTextContent('Asha Ramanathan'),
    );
  });

  it('drops the previous profile cached data when switching', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderProvider(queryClient);

    await waitFor(() =>
      expect(screen.getByTestId('active')).toHaveTextContent('Asha Ramanathan'),
    );

    // Stand in for a cached report belonging to the profile that is about to be switched away.
    queryClient.setQueryData(['profile', 'pp-owner', 'reports'], ['owner-report']);

    await user.click(screen.getByRole('button', { name: 'switch-Ravi Junior' }));

    await waitFor(() => expect(screen.getByTestId('active')).toHaveTextContent('Ravi Junior'));
    expect(queryClient.getQueryData(['profile', 'pp-owner', 'reports'])).toBeUndefined();
  });

  it('reports the switch to the server so it can be audited', async () => {
    const user = userEvent.setup();
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderProvider(queryClient);

    await waitFor(() =>
      expect(screen.getByTestId('active')).toHaveTextContent('Asha Ramanathan'),
    );
    await user.click(screen.getByRole('button', { name: 'switch-Ravi Junior' }));

    await waitFor(() => expect(vi.mocked(activateProfile)).toHaveBeenCalledWith('pp-child'));
  });

  it('ignores a stored profile id that this account does not own', async () => {
    window.localStorage.setItem('hiq.activeProfileId', 'pp-someone-elses');
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    renderProvider(queryClient);

    await waitFor(() =>
      expect(screen.getByTestId('active')).toHaveTextContent('Asha Ramanathan'),
    );
  });
});
