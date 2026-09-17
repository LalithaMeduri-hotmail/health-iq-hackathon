/**
 * Session token acquisition (frontend.instructions.md).
 *
 * The account module (`features/auth/`) authenticates via username/mobile/email + PIN; the
 * backend sets the session as an HttpOnly cookie (`api/auth.py`), which `apiClient.ts` sends via
 * `credentials: 'include'`. Nothing here ever stores a token in JS-accessible storage - per
 * frontend.instructions.md, secrets must never be persisted in `localStorage`/`sessionStorage`.
 *
 * Locally (VITE_DEMO_MODE=true), requests fall back to a stub user header when no session cookie
 * is present, so the app is still usable without signing in - see `features/auth/`.
 */

export const isDemoMode = import.meta.env.VITE_DEMO_MODE !== 'false';

// Signing out must mean signed out. The demo stub header would otherwise re-identify the caller on
// the very next request whenever the backend is also in demo mode, so an explicit sign-out
// suppresses it for the rest of the page session.
let demoIdentitySuppressed = false;

/** True while the demo stub user may stand in for a real session. */
export function isDemoIdentityAllowed(): boolean {
  return isDemoMode && !demoIdentitySuppressed;
}

export function suppressDemoIdentity(): void {
  demoIdentitySuppressed = true;
}

/** Re-enables the stub after a deliberate sign-in attempt. */
export function allowDemoIdentity(): void {
  demoIdentitySuppressed = false;
}

/** Always `null`: auth is carried by the HttpOnly session cookie, never a bearer token in JS. */
export async function getAccessToken(): Promise<string | null> {
  return null;
}
