import { describe, expect, it } from 'vitest';

import { createI18n } from './instance';
import { detectLocale, isAppLocale, languageOf } from './locales';
import { resources } from './resources';

interface Tree {
  readonly [key: string]: string | Tree;
}

function flatten(tree: Tree, prefix = ''): Map<string, string> {
  const entries = new Map<string, string>();
  for (const [key, value] of Object.entries(tree)) {
    const path = prefix === '' ? key : `${prefix}.${key}`;
    if (typeof value === 'string') {
      entries.set(path, value);
    } else {
      for (const [inner, text] of flatten(value, path)) {
        entries.set(inner, text);
      }
    }
  }
  return entries;
}

const flat = {
  es: flatten(resources.es.translation),
  pt: flatten(resources.pt.translation),
  en: flatten(resources.en.translation),
};

describe('locale files', () => {
  it.each(['pt', 'en'] as const)('%s has exactly the Spanish key set', (language) => {
    expect([...flat[language].keys()].sort()).toEqual([...flat.es.keys()].sort());
  });

  it.each(['es', 'pt', 'en'] as const)('%s has no empty strings', (language) => {
    for (const [key, text] of flat[language]) {
      expect(text.trim(), key).not.toBe('');
    }
  });

  it.each(['es', 'pt', 'en'] as const)('%s uses no em or en dashes and no emoji', (language) => {
    for (const [key, text] of flat[language]) {
      expect(text, key).not.toMatch(/[\u2013\u2014]/);
      expect(text, key).not.toMatch(/\p{Extended_Pictographic}/u);
    }
  });

  it.each(['es', 'pt', 'en'] as const)('%s keeps the same interpolation variables', (language) => {
    const variables = (text: string) =>
      [...text.matchAll(/\{\{(\w+)\}\}/g)].map((m) => m[1]).sort();
    for (const [key, text] of flat.es) {
      expect(variables(flat[language].get(key) ?? ''), key).toEqual(variables(text));
    }
  });

  it.each(['es', 'pt', 'en'] as const)(
    '%s states the hosted-model cost and that the model does not phrase replies',
    (language) => {
      const cost = flat[language].get('supervision.evaluation.costNote') ?? '';
      expect(cost).toContain('0.0013 USD');
      expect(cost).toContain('0.0019 USD');
      expect(cost).toMatch(/Azure/);
      const intro = flat[language].get('supervision.llm.intro') ?? '';
      expect(intro).not.toMatch(/phrases|redacta|redige/);
      expect(intro).toMatch(/embedding/);
    },
  );

  it('pluralizes per language', () => {
    const i18n = createI18n('pt-BR');
    expect(i18n.t('auth.attemptsRemaining', { count: 1 })).toBe('Resta 1 tentativa.');
    expect(i18n.t('auth.attemptsRemaining', { count: 3 })).toBe('Restam 3 tentativas.');
  });
});

describe('locale detection', () => {
  it('prefers an exact tag, then the language, then Mexican Spanish', () => {
    expect(detectLocale(['es-AR', 'en'])).toBe('es-AR');
    expect(detectLocale(['pt-PT'])).toBe('pt-BR');
    expect(detectLocale(['fr-FR', 'en-GB'])).toBe('en-US');
    expect(detectLocale(['de-DE'])).toBe('es-MX');
    expect(detectLocale([])).toBe('es-MX');
  });

  it('recognizes only the supported locales', () => {
    expect(isAppLocale('es-CO')).toBe(true);
    expect(isAppLocale('es-ES')).toBe(false);
    expect(isAppLocale(3)).toBe(false);
    expect(languageOf('pt-BR')).toBe('pt');
  });
});
