import type es from './locales/es.json';

// Typed keys: t('auth.sendCode') compiles, t('auth.sendcode') does not.
declare module 'i18next' {
  interface CustomTypeOptions {
    defaultNS: 'translation';
    resources: { translation: typeof es };
  }
}
