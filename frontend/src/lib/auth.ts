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

/** Always `null`: auth is carried by the HttpOnly session cookie, never a bearer token in JS. */
export async function getAccessToken(): Promise<string | null> {
  return null;
}
