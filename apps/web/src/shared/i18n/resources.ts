import en from './locales/en.json';
import es from './locales/es.json';
import pt from './locales/pt.json';

/** Spanish is the source of truth for the key set; locales.test.ts fails when pt or en differ from it. */
export const resources = {
  es: { translation: es },
  pt: { translation: pt },
  en: { translation: en },
} as const;
