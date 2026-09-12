/**
 * Upload-consent persistence (frontend.instructions.md consent-gate requirement + "no secrets in
 * localStorage" - a consent flag isn't a secret, so persisting it here is fine, unlike auth/theme
 * being separate concerns already handled by `lib/theme.ts`/`features/auth`).
 *
 * Bump `CONSENT_VERSION` whenever the consent copy changes so returning users are re-prompted.
 */

const CONSENT_STORAGE_KEY = 'healthiq-consent-version';

export const CONSENT_VERSION = '2026-08-27';

export function getStoredConsentVersion(): string | null {
  return window.localStorage.getItem(CONSENT_STORAGE_KEY);
}

export function storeConsentVersion(version: string): void {
  window.localStorage.setItem(CONSENT_STORAGE_KEY, version);
}

export function hasCurrentConsent(): boolean {
  return getStoredConsentVersion() === CONSENT_VERSION;
}
