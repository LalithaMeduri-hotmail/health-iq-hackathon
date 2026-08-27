/**
 * MSAL configuration + token acquisition (frontend.instructions.md).
 *
 * Locally (VITE_DEMO_MODE=true) requests use a stub user header instead of a real Entra token -
 * see docs/team-plan.md cut-list item 1. Wire real MSAL login before any non-demo use.
 */

export const isDemoMode = import.meta.env.VITE_DEMO_MODE !== 'false';

/** TODO(D4): replace with `PublicClientApplication` from `@azure/msal-browser` once Entra login is wired. */
export async function getAccessToken(): Promise<string | null> {
  if (isDemoMode) {
    return null;
  }
  throw new Error('MSAL login not yet implemented - see frontend/src/lib/auth.ts');
}
