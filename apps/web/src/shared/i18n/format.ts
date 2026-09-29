import type { AppLocale } from './locales';

/** An amount as the API sends it: a decimal string (never a float) and an ISO 4217 currency. */
export interface MoneyValue {
  readonly amount: string;
  readonly currency: string;
}

export interface Formatters {
  readonly locale: AppLocale;
  /** Currency with the locale's symbol and grouping; the decimal string is formatted exactly, never as a float. */
  money: (value: MoneyValue) => string;
  number: (value: number) => string;
  /** A calendar date, for example an as-of date or a due date. */
  date: (iso: string) => string;
  /** A date with the time, in the viewer's time zone. */
  dateTime: (iso: string) => string;
  time: (iso: string) => string;
  /** "in 5 minutes", "2 hours ago", relative to `now`. */
  relative: (iso: string, now?: Date) => string;
  /** A countdown as m:ss, for code expiry. */
  countdown: (seconds: number) => string;
}

const RELATIVE_STEPS: readonly [Intl.RelativeTimeFormatUnit, number][] = [
  ['second', 60],
  ['minute', 60],
  ['hour', 24],
  ['day', 30],
  ['month', 12],
  ['year', Number.POSITIVE_INFINITY],
];

/** Digits after the decimal point, ignoring trailing zeros: "12.50" has 1, "12.00" has 0. */
function significantDecimals(amount: string): number {
  const fraction = amount.split('.')[1] ?? '';
  return fraction.replace(/0+$/, '').length;
}

export function createFormatters(locale: AppLocale, timeZone?: string): Formatters {
  const zone = timeZone === undefined ? {} : { timeZone };
  const moneyFormats = new Map<string, Intl.NumberFormat>();
  const numberFormat = new Intl.NumberFormat(locale);
  const dateFormat = new Intl.DateTimeFormat(locale, { dateStyle: 'medium', ...zone });
  const dateTimeFormat = new Intl.DateTimeFormat(locale, {
    dateStyle: 'medium',
    timeStyle: 'short',
    ...zone,
  });
  const timeFormat = new Intl.DateTimeFormat(locale, { timeStyle: 'short', ...zone });
  const relativeFormat = new Intl.RelativeTimeFormat(locale, { numeric: 'auto' });

  const moneyFormat = (currency: string, decimals: number): Intl.NumberFormat => {
    const key = `${currency}:${String(decimals)}`;
    let format = moneyFormats.get(key);
    if (format === undefined) {
      const standard = new Intl.NumberFormat(locale, { style: 'currency', currency });
      // Never round away digits the API sent: a locale that shows COP without cents still shows 1.234.567,50
      // when the amount has cents.
      const usual = standard.resolvedOptions().maximumFractionDigits ?? 2;
      format =
        decimals > usual
          ? new Intl.NumberFormat(locale, {
              style: 'currency',
              currency,
              minimumFractionDigits: Math.max(decimals, 2),
              maximumFractionDigits: Math.max(decimals, 2),
            })
          : standard;
      moneyFormats.set(key, format);
    }
    return format;
  };

  return {
    locale,
    money: ({ amount, currency }) =>
      moneyFormat(currency, significantDecimals(amount)).format(
        amount as Intl.StringNumericLiteral,
      ),
    number: (value) => numberFormat.format(value),
    date: (iso) => dateFormat.format(new Date(iso)),
    dateTime: (iso) => dateTimeFormat.format(new Date(iso)),
    time: (iso) => timeFormat.format(new Date(iso)),
    relative: (iso, now = new Date()) => {
      let value = (new Date(iso).getTime() - now.getTime()) / 1000;
      for (const [unit, size] of RELATIVE_STEPS) {
        if (Math.abs(value) < size) {
          return relativeFormat.format(Math.round(value), unit);
        }
        value /= size;
      }
      return relativeFormat.format(Math.round(value), 'year');
    },
    countdown: (seconds) => {
      const safe = Math.max(0, Math.floor(seconds));
      return `${String(Math.floor(safe / 60))}:${String(safe % 60).padStart(2, '0')}`;
    },
  };
}
