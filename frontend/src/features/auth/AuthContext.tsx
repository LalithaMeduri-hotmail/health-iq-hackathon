/**
 * Cross-cutting auth/session state (frontend.instructions.md: "Introduce a global store ... only
 * for genuinely cross-cutting client state (auth/session, consent status, theme)").
 *
 * Session presence is derived from `GET /api/v1/auth/me`: a 401 means "not signed in" (demo/guest
 * use is still fully functional - see `lib/auth.ts`), not an application error.
 */

import { createContext, useContext, useMemo } from 'react';
import type { ReactNode } from 'react';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

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

  const meQuery = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: fetchCurrentAccount,
    retry: false,
    staleTime: 60_000,
  });

  const loginMutation = useMutation({
    mutationFn: loginAccount,
    onSuccess: (response) =>
      queryClient.setQueryData(['auth', 'me'], { ...response, data: response.data.account }),
  });

  const registerMutation = useMutation({
    mutationFn: registerAccount,
    onSuccess: (response) =>
      queryClient.setQueryData(['auth', 'me'], { ...response, data: response.data.account }),
  });

  const logoutMutation = useMutation({
    mutationFn: logoutAccount,
    onSuccess: () => queryClient.setQueryData(['auth', 'me'], undefined),
  });

  const value = useMemo<AuthContextValue>(
    () => ({
      account: meQuery.data?.data ?? null,
      isLoading: meQuery.isLoading,
      login: async (input) => (await loginMutation.mutateAsync(input)).data.account,
      register: async (input) => (await registerMutation.mutateAsync(input)).data.account,
      logout: async () => {
        await logoutMutation.mutateAsync();
      },
    }),
    [meQuery.data, meQuery.isLoading, loginMutation, registerMutation, logoutMutation],
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
