import { createContext, use } from 'react';

import type { Formatters } from './format';
import type { AppLocale, Language } from './locales';

export interface LocaleContextValue {
  readonly locale: AppLocale;
  readonly language: Language;
  readonly format: Formatters;
  /** The time zone formatters use; undefined means the viewer's. */
  readonly timeZone: string | undefined;
  readonly setLocale: (locale: AppLocale) => void;
}

export const LocaleContext = createContext<LocaleContextValue | null>(null);

export function useLocale(): LocaleContextValue {
  const context = use(LocaleContext);
  if (context === null) {
    throw new Error('useLocale must be used inside <LocaleProvider>');
  }
  return context;
}

/** The formatters for the current locale: money, dates, relative time, countdowns. */
export function useFormat(): Formatters {
  return useLocale().format;
}
