/**
 * Cross-cutting auth/session state (frontend.instructions.md: "Introduce a global store ... only
 * for genuinely cross-cutting client state (auth/session, consent status, theme)").
 *
 * Session presence is derived from `GET /api/v1/auth/me`: a 401 means "not signed in" (demo/guest
 * use is still fully functional - see `lib/auth.ts`), not an application error. A 401 from any
 * *other* endpoint does mean the session died mid-use, and is handled here by ending the session
 * and sending the user back to sign in.
 */

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';

import { setUnauthorizedHandler } from '@/lib/apiClient';
import { allowDemoIdentity, suppressDemoIdentity } from '@/lib/auth';

import { fetchCurrentAccount, loginAccount, logoutAccount, registerAccount } from './api';
import type { AccountPublic, LoginInput, RegisterInput } from './types';

interface AuthContextValue {
  account: AccountPublic | null;
  isLoading: boolean;
  login: (input: LoginInput) => Promise<AccountPublic>;
  register: (input: RegisterInput) => Promise<AccountPublic>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  // Ending a session is a local fact, not something to re-derive from the server. Without it,
  // clearing the cache just makes the still-mounted `me` query refetch and the user pops back in.
  const [isSessionEnded, setIsSessionEnded] = useState(false);

  const meQuery = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: fetchCurrentAccount,
    retry: false,
    staleTime: 60_000,
    enabled: !isSessionEnded,
  });

  /**
   * Everything cached is this person's health data, so ending a session clears the whole cache
   * rather than just the session key - otherwise the next person to sign in on this browser would
   * see the previous one's reports until each query happened to refetch.
   */
  const endSession = useCallback(() => {
    setIsSessionEnded(true);
    suppressDemoIdentity();
    queryClient.clear();
  }, [queryClient]);

  const resumeSession = useCallback(() => {
    setIsSessionEnded(false);
    allowDemoIdentity();
  }, []);

  const loginMutation = useMutation({
    mutationFn: loginAccount,
    onSuccess: (response) => {
      resumeSession();
      queryClient.setQueryData(['auth', 'me'], { ...response, data: response.data.account });
    },
  });

  const registerMutation = useMutation({
    mutationFn: registerAccount,
    onSuccess: (response) => {
      resumeSession();
      queryClient.setQueryData(['auth', 'me'], { ...response, data: response.data.account });
    },
  });

  const logoutMutation = useMutation({ mutationFn: logoutAccount });

  // An expired or invalidated cookie surfaces as a 401 on a normal page request; treat it exactly
  // like a sign-out and say so, instead of leaving a dead "Try again" on the page.
  useEffect(() => {
    setUnauthorizedHandler(() => {
      endSession();
      navigate('/login?reason=expired', { replace: true });
    });
    return () => setUnauthorizedHandler(null);
  }, [endSession, navigate]);

  const value = useMemo<AuthContextValue>(
    () => ({
      account: isSessionEnded ? null : (meQuery.data?.data ?? null),
      isLoading: !isSessionEnded && meQuery.isLoading,
      login: async (input) => (await loginMutation.mutateAsync(input)).data.account,
      register: async (input) => (await registerMutation.mutateAsync(input)).data.account,
      logout: async () => {
        try {
          await logoutMutation.mutateAsync();
        } catch {
          // Already signed out, offline, or the session had expired anyway - all end the same way.
        } finally {
          // The cookie is gone server-side either way; never strand the user looking signed in.
          endSession();
          navigate('/login', { replace: true });
        }
      },
    }),
    [
      isSessionEnded,
      meQuery.data,
      meQuery.isLoading,
      loginMutation,
      registerMutation,
      logoutMutation,
      endSession,
      navigate,
    ],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
