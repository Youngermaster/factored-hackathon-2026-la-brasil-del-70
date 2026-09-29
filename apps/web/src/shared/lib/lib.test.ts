import { afterEach, describe, expect, it, vi } from 'vitest';

import { cx } from './cx';
import { PREFERENCES_KEY, readPreferences, writePreferences } from './preferences';
import { safeNextPath } from './safe-next';

describe('cx', () => {
  it('joins the truthy class names only', () => {
    expect(cx('a', false, null, undefined, '', 'b')).toBe('a b');
  });
});

describe('preferences', () => {
  afterEach(() => {
    window.localStorage.clear();
  });

  it('round-trips the theme and locale', () => {
    writePreferences({ theme: 'dark' });
    writePreferences({ locale: 'pt-BR' });
    expect(readPreferences()).toEqual({ theme: 'dark', locale: 'pt-BR' });
  });

  it('ignores malformed or unknown values', () => {
    window.localStorage.setItem(PREFERENCES_KEY, JSON.stringify({ theme: 'sepia', locale: 7 }));
    expect(readPreferences()).toEqual({});
    window.localStorage.setItem(PREFERENCES_KEY, '[1,2]');
    expect(readPreferences()).toEqual({});
    window.localStorage.setItem(PREFERENCES_KEY, '{not json');
    expect(readPreferences()).toEqual({});
  });

  it('keeps working when storage throws', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked');
    });
    expect(() => {
      writePreferences({ theme: 'light' });
    }).not.toThrow();
  });
});

describe('safeNextPath', () => {
  it.each([
    ['/', '/'],
    ['/console', '/console'],
    ['/?conversation=c-123', '/?conversation=c-123'],
  ])('keeps the same-app path %s', (candidate, expected) => {
    expect(safeNextPath(candidate, '/home')).toBe(expected);
  });

  it.each([
    null,
    '',
    'https://evil.example/',
    '//evil.example/path',
    '/\\evil.example',
    'javascript:alert(1)',
    '/login?next=/',
  ])('falls back for %s', (candidate) => {
    expect(safeNextPath(candidate, '/home')).toBe('/home');
  });
});
