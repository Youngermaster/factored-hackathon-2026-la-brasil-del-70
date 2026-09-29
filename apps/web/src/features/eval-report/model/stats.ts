/**
 * Intervals for the published counts, computed in the browser so every figure carries one. Proportions use the
 * Wilson score interval (95%); zero events use the exact one-sided 95% upper bound, 1 - 0.05^(1/n). Both depend only
 * on the count and the denominator the summary publishes.
 */
const Z_95 = 1.959963984540054;

/** Cells with fewer cases than this are flagged small: their intervals are wide and their rates unstable. */
export const SMALL_CELL = 30;

export interface Proportion {
  readonly count: number;
  readonly denominator: number;
  readonly rate: number;
  readonly low: number;
  readonly high: number;
  /** True when the count is zero: `high` is then the one-sided upper bound and `low` is zero. */
  readonly zeroEvents: boolean;
  readonly small: boolean;
}

export function wilson(
  count: number,
  denominator: number,
  z = Z_95,
): { low: number; high: number } {
  const p = count / denominator;
  const z2 = z * z;
  const centre = p + z2 / (2 * denominator);
  const margin = z * Math.sqrt((p * (1 - p)) / denominator + z2 / (4 * denominator * denominator));
  const scale = 1 + z2 / denominator;
  return {
    low: Math.max(0, (centre - margin) / scale),
    high: Math.min(1, (centre + margin) / scale),
  };
}

export function zeroEventUpperBound(denominator: number): number {
  return 1 - Math.pow(0.05, 1 / denominator);
}

/** A count over its denominator with its interval, or null when the denominator is zero (not defined). */
export function proportion(metric: { count: number; denominator: number }): Proportion | null {
  const { count, denominator } = metric;
  if (denominator <= 0) {
    return null;
  }
  const zeroEvents = count === 0;
  const interval = zeroEvents
    ? { low: 0, high: zeroEventUpperBound(denominator) }
    : wilson(count, denominator);
  return {
    count,
    denominator,
    rate: count / denominator,
    ...interval,
    zeroEvents,
    small: denominator < SMALL_CELL,
  };
}
