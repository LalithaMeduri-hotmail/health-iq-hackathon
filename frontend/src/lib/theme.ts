/**
 * Dark/light theme persistence (frontend.instructions.md calls out "theme" as one of the few
 * cross-cutting concerns worth a global store). The active theme is applied as
 * `<html data-theme="light|dark">`, which `styles/theme.css` keys its dark overrides off of.
 *
 * Not a secret, so - unlike auth/session data - this is fine to keep in `localStorage`.
 */

export type Theme = 'light' | 'dark';

const STORAGE_KEY = 'healthiq-theme';

export function getSystemTheme(): Theme {
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
}

export function getStoredTheme(): Theme | null {
  const stored = window.localStorage.getItem(STORAGE_KEY);
  return stored === 'light' || stored === 'dark' ? stored : null;
}

export function resolveInitialTheme(): Theme {
  return getStoredTheme() ?? getSystemTheme();
}

export function applyTheme(theme: Theme): void {
  document.documentElement.setAttribute('data-theme', theme);
  window.localStorage.setItem(STORAGE_KEY, theme);
}
