import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';

import { readPreferences, writePreferences, type ThemePreference } from '@/shared/lib/preferences';

import { ThemeContext, type ResolvedTheme } from './context';

const DARK_QUERY = '(prefers-color-scheme: dark)';

function systemTheme(): ResolvedTheme {
  return typeof window.matchMedia === 'function' && window.matchMedia(DARK_QUERY).matches
    ? 'dark'
    : 'light';
}

/**
 * Owns the theme: `system`, `light`, or `dark`, persisted as a display preference. public/theme-init.js applies
 * the same choice before first paint; this provider keeps `<html data-theme>` in sync afterwards and follows the
 * operating system while the preference is `system`.
 */
export function ThemeProvider({
  children,
  initialPreference,
}: {
  children: ReactNode;
  initialPreference?: ThemePreference;
}) {
  const [preference, setPreferenceState] = useState<ThemePreference>(
    () => initialPreference ?? readPreferences().theme ?? 'system',
  );
  const [system, setSystem] = useState<ResolvedTheme>(systemTheme);

  useEffect(() => {
    if (typeof window.matchMedia !== 'function') {
      return undefined;
    }
    const query = window.matchMedia(DARK_QUERY);
    const onChange = () => {
      setSystem(query.matches ? 'dark' : 'light');
    };
    query.addEventListener('change', onChange);
    return () => {
      query.removeEventListener('change', onChange);
    };
  }, []);

  const resolved: ResolvedTheme = preference === 'system' ? system : preference;

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', resolved);
  }, [resolved]);

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next);
    writePreferences({ theme: next });
  }, []);

  const value = useMemo(
    () => ({ preference, resolved, setPreference }),
    [preference, resolved, setPreference],
  );
  return <ThemeContext value={value}>{children}</ThemeContext>;
}
