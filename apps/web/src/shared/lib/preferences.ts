/**
 * Per-viewer display preferences (theme and locale) in localStorage. This is the only module allowed to touch web
 * storage (eslint.config.js scopes the exception to this file): it never holds session data, tokens, or customer
 * data. public/theme-init.js reads the same record before first paint. Storage can be missing or throw (private
 * windows, blocked site data), so every access is guarded and the app works without it.
 */
export type ThemePreference = 'system' | 'light' | 'dark';

export interface Preferences {
  readonly theme?: ThemePreference;
  readonly locale?: string;
}

export const PREFERENCES_KEY = 'bank-agent.preferences.v1';

const THEMES: readonly string[] = ['system', 'light', 'dark'];

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function readPreferences(): Preferences {
  try {
    const parsed: unknown = JSON.parse(window.localStorage.getItem(PREFERENCES_KEY) ?? '{}');
    if (!isRecord(parsed)) {
      return {};
    }
    const { theme, locale } = parsed;
    return {
      ...(typeof theme === 'string' && THEMES.includes(theme)
        ? { theme: theme as ThemePreference }
        : {}),
      ...(typeof locale === 'string' ? { locale } : {}),
    };
  } catch {
    return {};
  }
}

export function writePreferences(patch: Preferences): void {
  try {
    window.localStorage.setItem(
      PREFERENCES_KEY,
      JSON.stringify({ ...readPreferences(), ...patch }),
    );
  } catch {
    // Storage is unavailable; the preference lasts for this page view only.
  }
}
