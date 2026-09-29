import i18next, { type i18n } from 'i18next';
import { initReactI18next } from 'react-i18next';

import { languageOf, type AppLocale } from './locales';
import { resources } from './resources';

/**
 * A fresh i18next instance per app root (and per test), initialized synchronously from bundled resources, so the
 * first render already has its copy and no request is made for translations.
 */
export function createI18n(locale: AppLocale): i18n {
  const instance = i18next.createInstance();
  void instance.use(initReactI18next).init({
    resources,
    lng: languageOf(locale),
    fallbackLng: 'es',
    supportedLngs: ['es', 'pt', 'en'],
    initAsync: false,
    returnNull: false,
    // React escapes text already; i18next must not escape a second time.
    interpolation: { escapeValue: false },
  });
  return instance;
}
