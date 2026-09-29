import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { I18nextProvider } from 'react-i18next';

import { readPreferences, writePreferences } from '@/shared/lib/preferences';

import { LocaleContext } from './context';
import { createFormatters } from './format';
import { createI18n } from './instance';
import { detectLocale, isAppLocale, languageOf, type AppLocale } from './locales';

function initialLocale(): AppLocale {
  const stored = readPreferences().locale;
  return isAppLocale(stored) ? stored : detectLocale(navigator.languages);
}

/**
 * Provides the copy (i18next) and the `Intl` formatters for one locale, keeps `<html lang>` in step, and persists
 * the choice as a display preference.
 */
export function LocaleProvider({
  children,
  locale: fixedLocale,
  timeZone,
}: {
  children: ReactNode;
  /** Tests pin a locale; the app detects it. */
  locale?: AppLocale;
  /** Tests pin a time zone; the app uses the viewer's. */
  timeZone?: string;
}) {
  const [locale, setLocaleState] = useState<AppLocale>(() => fixedLocale ?? initialLocale());
  const [i18n] = useState(() => createI18n(locale));
  const language = languageOf(locale);

  useEffect(() => {
    void i18n.changeLanguage(language);
    document.documentElement.lang = language;
  }, [i18n, language]);

  const setLocale = useCallback((next: AppLocale) => {
    setLocaleState(next);
    writePreferences({ locale: next });
  }, []);

  const value = useMemo(
    () => ({ locale, language, format: createFormatters(locale, timeZone), setLocale }),
    [locale, language, timeZone, setLocale],
  );

  return (
    <I18nextProvider i18n={i18n}>
      <LocaleContext value={value}>{children}</LocaleContext>
    </I18nextProvider>
  );
}
