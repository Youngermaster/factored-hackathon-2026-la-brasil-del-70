import type { i18n } from 'i18next';
import { useMemo, type ReactNode } from 'react';
import { I18nextProvider } from 'react-i18next';

import { LocaleContext, useLocale } from './context';
import { createFormatters } from './format';
import { createI18n } from './instance';
import type { AppLocale, Language } from './locales';

/** The locale a scope formats with when its language differs from the viewer's. */
const DEFAULT_LOCALE_OF: Record<Language, AppLocale> = {
  es: 'es-MX',
  pt: 'pt-BR',
  en: 'en-US',
};

// One i18next instance per language, shared by every scope: scopes only read copy, they never change language.
const instances = new Map<Language, i18n>();

function instanceFor(language: Language): i18n {
  let instance = instances.get(language);
  if (instance === undefined) {
    instance = createI18n(DEFAULT_LOCALE_OF[language]);
    instances.set(language, instance);
  }
  return instance;
}

/**
 * Renders its children in another language: copy from that language's file and `Intl` formats for its default
 * locale. A conversation turn in Portuguese reads in Portuguese whatever the viewer's chrome language is. When the
 * language is the viewer's own, the viewer's locale (and region) stays.
 */
export function LanguageScope({
  language,
  children,
}: {
  readonly language: Language;
  readonly children: ReactNode;
}) {
  const outer = useLocale();
  const same = outer.language === language;
  const value = useMemo(() => {
    const locale = DEFAULT_LOCALE_OF[language];
    return { ...outer, locale, language, format: createFormatters(locale, outer.timeZone) };
  }, [outer, language]);
  if (same) {
    return children;
  }
  return (
    <I18nextProvider i18n={instanceFor(language)}>
      <LocaleContext value={value}>{children}</LocaleContext>
    </I18nextProvider>
  );
}
