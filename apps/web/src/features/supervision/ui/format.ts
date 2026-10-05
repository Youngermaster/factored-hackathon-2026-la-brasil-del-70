import { useMemo } from 'react';

import { useFormat } from '@/shared/i18n';

/**
 * Number formats for published evidence: decimals keep up to four digits so a Brier score of 0.1935 is not rounded
 * to 0.194, and rates are shown as percentages with one decimal.
 */
export function useEvidenceFormat() {
  const format = useFormat();
  return useMemo(() => {
    const decimal = new Intl.NumberFormat(format.locale, { maximumFractionDigits: 4 });
    const percent = new Intl.NumberFormat(format.locale, {
      style: 'percent',
      maximumFractionDigits: 1,
    });
    return {
      ...format,
      decimal: (value: number) => decimal.format(value),
      percent: (rate: number) => percent.format(rate),
    };
  }, [format]);
}
