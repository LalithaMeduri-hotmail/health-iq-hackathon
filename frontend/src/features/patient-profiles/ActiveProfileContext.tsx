/**
 * Active patient profile - cross-cutting client state (frontend.instructions.md allows a global
 * store for genuinely cross-cutting concerns).
 *
 * Only the *identifier* of the active profile is kept in client state. Medical history is never
 * mirrored here: it stays in the query cache, keyed by profile, so switching person cannot leave
 * a stale report on screen.
 *
 * Switching profiles deliberately clears the whole query cache. Removing only the keys we can
 * name would leave anything added later silently leaking one family member's data into another's
 * dashboard, and a refetch is far cheaper than that mistake.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';

import { useAuth } from '@/features/auth';
import { isDemoIdentityAllowed } from '@/lib/auth';

import { activateProfile, fetchPatientProfiles } from './api';
import type { PatientProfile } from './types';

const ACTIVE_PROFILE_STORAGE_KEY = 'hiq.activeProfileId';

interface ActiveProfileContextValue {
  profiles: PatientProfile[];
  activeProfile: PatientProfile | null;
  activeProfileId: string | null;
  isLoading: boolean;
  error: unknown;
  /** True when the account has no usable profile yet and must complete onboarding. */
  needsOnboarding: boolean;
  setActiveProfile: (profileId: string) => void;
  refresh: () => Promise<unknown>;
}

const ActiveProfileContext = createContext<ActiveProfileContextValue | null>(null);

function readStoredProfileId(): string | null {
  try {
    return window.localStorage.getItem(ACTIVE_PROFILE_STORAGE_KEY);
  } catch {
    return null;
  }
}

function storeProfileId(profileId: string | null): void {
  try {
    if (profileId) {
      window.localStorage.setItem(ACTIVE_PROFILE_STORAGE_KEY, profileId);
    } else {
      window.localStorage.removeItem(ACTIVE_PROFILE_STORAGE_KEY);
    }
  } catch {
    /* A browser with storage disabled still works; the choice just does not survive a reload. */
  }
}

export function ActiveProfileProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const { account, isLoading: isAuthLoading } = useAuth();
  const [selectedId, setSelectedId] = useState<string | null>(() => readStoredProfileId());

  // A signed-out visitor has no profiles to fetch. Asking anyway would 401, and `apiClient` turns
  // an unexpected 401 into "your session expired" plus a redirect - which would throw a browsing
  // visitor off every public page.
  const isIdentified = !isAuthLoading && (account !== null || isDemoIdentityAllowed());

  const profilesQuery = useQuery({
    queryKey: ['patient-profiles'],
    queryFn: fetchPatientProfiles,
    retry: false,
    staleTime: 30_000,
    enabled: isIdentified,
  });

  const profiles = useMemo(
    () => profilesQuery.data?.data.profiles ?? [],
    [profilesQuery.data],
  );

  /**
   * A stored id is untrusted input: it may name a profile that was archived, deleted, or that
   * belongs to whoever used this browser last. Only ever resolve it against the list the server
   * just returned for *this* session.
   */
  const activeProfile = useMemo(() => {
    if (profiles.length === 0) {
      return null;
    }
    const selected = profiles.find(
      (profile) => profile.id === selectedId && profile.status === 'active',
    );
    if (selected) {
      return selected;
    }
    const owner = profiles.find((profile) => profile.isAccountOwnerProfile);
    return owner ?? profiles.find((profile) => profile.status === 'active') ?? null;
  }, [profiles, selectedId]);

  // Keep storage consistent with what actually resolved, so a stale id is not retried forever.
  useEffect(() => {
    if (activeProfile && activeProfile.id !== selectedId) {
      setSelectedId(activeProfile.id);
      storeProfileId(activeProfile.id);
    }
  }, [activeProfile, selectedId]);

  const setActiveProfile = useCallback(
    (profileId: string) => {
      if (profileId === selectedId) {
        return;
      }
      // Cancel in-flight requests first: a response for the previous profile that lands after
      // the switch would otherwise repopulate the cache with the wrong person's data.
      void queryClient.cancelQueries();
      queryClient.clear();

      setSelectedId(profileId);
      storeProfileId(profileId);

      // Called directly rather than through a mutation: `clear()` empties the mutation cache too,
      // which would silently discard this audit ping.
      void activateProfile(profileId).catch(() => {
        /* Recording the switch is best-effort; it must never block the user. */
      });
    },
    [queryClient, selectedId],
  );

  const value = useMemo<ActiveProfileContextValue>(
    () => ({
      profiles,
      activeProfile,
      activeProfileId: activeProfile?.id ?? null,
      isLoading: isAuthLoading || profilesQuery.isLoading,
      error: profilesQuery.error,
      needsOnboarding:
        isIdentified && !profilesQuery.isLoading && !profilesQuery.error && profiles.length === 0,
      setActiveProfile,
      refresh: () => queryClient.invalidateQueries({ queryKey: ['patient-profiles'] }),
    }),
    [
      activeProfile,
      isAuthLoading,
      isIdentified,
      profiles,
      profilesQuery.error,
      profilesQuery.isLoading,
      queryClient,
      setActiveProfile,
    ],
  );

  return <ActiveProfileContext.Provider value={value}>{children}</ActiveProfileContext.Provider>;
}

export function useActiveProfile(): ActiveProfileContextValue {
  const context = useContext(ActiveProfileContext);
  if (!context) {
    throw new Error('useActiveProfile must be used inside an ActiveProfileProvider');
  }
  return context;
}

/** Same state, but tolerates being rendered outside the provider (returns `null`). */
export function useActiveProfileOptional(): ActiveProfileContextValue | null {
  return useContext(ActiveProfileContext);
}
