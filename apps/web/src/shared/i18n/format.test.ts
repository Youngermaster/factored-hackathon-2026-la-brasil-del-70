import { describe, expect, it } from 'vitest';

import { createFormatters } from './format';
import { SUPPORTED_LOCALES } from './locales';

// Intl uses no-break spaces (U+00A0, U+202F) between parts; the expectations read better with plain spaces.
const plain = (text: string) => text.replace(/[\u00a0\u202f]/g, ' ');

const at = '2026-09-27T15:04:00Z';

describe('money', () => {
  it.each([
    ['es-MX', { amount: '1234567.5', currency: 'MXN' }, '$1,234,567.50'],
    ['es-CO', { amount: '1234567.5', currency: 'COP' }, '$ 1.234.567,50'],
    ['es-AR', { amount: '1234567.5', currency: 'ARS' }, '$ 1.234.567,50'],
    ['pt-BR', { amount: '1234567.5', currency: 'MXN' }, 'MX$ 1.234.567,50'],
    ['en-US', { amount: '1234567.5', currency: 'ARS' }, 'ARS 1,234,567.50'],
  ] as const)('%s formats %o', (locale, money, expected) => {
    expect(plain(createFormatters(locale, 'UTC').money(money))).toBe(expected);
  });

  it('keeps cents a locale would otherwise round away, and drops zero cents where the locale does', () => {
    const format = createFormatters('es-CO', 'UTC');
    expect(plain(format.money({ amount: '1234567.00', currency: 'COP' }))).toBe('$ 1.234.567');
    expect(plain(format.money({ amount: '10.125', currency: 'COP' }))).toBe('$ 10,125');
  });

  it('formats the decimal string exactly, without float rounding', () => {
    const format = createFormatters('en-US', 'UTC');
    expect(format.money({ amount: '9007199254740993.01', currency: 'USD' })).toBe(
      '$9,007,199,254,740,993.01',
    );
    expect(format.money({ amount: '-0.10', currency: 'USD' })).toBe('-$0.10');
  });
});

describe('dates and times', () => {
  it.each([
    ['es-MX', '27 sep 2026', '27 sep 2026, 3:04 p.m.'],
    ['es-CO', '27/09/2026', '27/09/2026, 3:04 p. m.'],
    ['es-AR', '27 sept 2026', '27 sept 2026, 3:04 p. m.'],
    ['pt-BR', '27 de set. de 2026', '27 de set. de 2026, 15:04'],
    ['en-US', 'Sep 27, 2026', 'Sep 27, 2026, 3:04 PM'],
  ] as const)('%s formats dates and date-times', (locale, date, dateTime) => {
    const format = createFormatters(locale, 'UTC');
    expect(plain(format.date(at))).toBe(date);
    expect(plain(format.dateTime(at))).toBe(dateTime);
  });

  it('honors the time zone', () => {
    expect(plain(createFormatters('es-MX', 'America/Mexico_City').time(at))).toBe('9:04 a.m.');
  });

  it('shows a date-only value as the same calendar day in every time zone', () => {
    expect(plain(createFormatters('es-MX', 'America/Mexico_City').day('2026-06-15'))).toBe(
      '15 jun 2026',
    );
    expect(plain(createFormatters('pt-BR', 'Asia/Tokyo').day('2026-06-15'))).toBe(
      '15 de jun. de 2026',
    );
  });

  it.each(SUPPORTED_LOCALES)('%s formats relative time in both directions', (locale) => {
    const format = createFormatters(locale, 'UTC');
    const now = new Date(at);
    const inFive = format.relative('2026-09-27T15:09:00Z', now);
    const twoHoursAgo = format.relative('2026-09-27T13:04:00Z', now);
    expect(inFive).toMatch(/5/);
    expect(twoHoursAgo).toMatch(/2/);
    expect(inFive).not.toBe(twoHoursAgo);
  });

  it('formats relative time per language', () => {
    const now = new Date(at);
    expect(createFormatters('es-AR', 'UTC').relative('2026-09-27T15:09:00Z', now)).toBe(
      'dentro de 5 minutos',
    );
    expect(createFormatters('pt-BR', 'UTC').relative('2026-09-27T13:04:00Z', now)).toBe(
      'há 2 horas',
    );
    expect(createFormatters('en-US', 'UTC').relative('2026-09-28T15:04:00Z', now)).toBe('tomorrow');
  });

  it('formats a countdown as m:ss and never below zero', () => {
    const format = createFormatters('es-MX');
    expect(format.countdown(299)).toBe('4:59');
    expect(format.countdown(5)).toBe('0:05');
    expect(format.countdown(-3)).toBe('0:00');
  });

  it('groups plain numbers per locale', () => {
    expect(plain(createFormatters('es-CO').number(12345.5))).toBe('12.345,5');
    expect(createFormatters('en-US').number(12345.5)).toBe('12,345.5');
  });
});
