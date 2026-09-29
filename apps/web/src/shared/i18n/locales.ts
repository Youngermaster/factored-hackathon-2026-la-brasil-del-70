/** The locales the app formats for. The language (es, pt, en) picks the copy; the full tag drives `Intl`. */
export const SUPPORTED_LOCALES = ['es-MX', 'es-CO', 'es-AR', 'pt-BR', 'en-US'] as const;

export type AppLocale = (typeof SUPPORTED_LOCALES)[number];
export type Language = 'es' | 'pt' | 'en';

export const DEFAULT_LOCALE: AppLocale = 'es-MX';

/** Native names, so each option is readable by the people who need it, whatever the current language. */
export const LOCALE_NAMES: Record<AppLocale, string> = {
  'es-MX': 'Español (México)',
  'es-CO': 'Español (Colombia)',
  'es-AR': 'Español (Argentina)',
  'pt-BR': 'Português (Brasil)',
  'en-US': 'English (United States)',
};

export function isAppLocale(value: unknown): value is AppLocale {
  return typeof value === 'string' && (SUPPORTED_LOCALES as readonly string[]).includes(value);
}

export function languageOf(locale: AppLocale): Language {
  return locale.slice(0, 2) as Language;
}

/** The first supported locale that matches the browser's list, by exact tag and then by language. */
export function detectLocale(preferred: readonly string[]): AppLocale {
  for (const tag of preferred) {
    const exact = SUPPORTED_LOCALES.find((locale) => locale.toLowerCase() === tag.toLowerCase());
    if (exact !== undefined) {
      return exact;
    }
  }
  for (const tag of preferred) {
    const language = tag.slice(0, 2).toLowerCase();
    const byLanguage = SUPPORTED_LOCALES.find((locale) => locale.startsWith(language));
    if (byLanguage !== undefined) {
      return byLanguage;
    }
  }
  return DEFAULT_LOCALE;
}
