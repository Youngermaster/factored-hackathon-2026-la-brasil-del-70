import { cx } from '@/shared/lib/cx';
import { useFormat, type MoneyValue } from '@/shared/i18n';

/** An exact amount in its own currency, formatted for the scope's locale (never summed across currencies). */
export function Amount({
  value,
  className,
}: {
  readonly value: MoneyValue;
  readonly className?: string;
}) {
  const format = useFormat();
  return (
    <span className={cx('font-mono tabular-nums whitespace-nowrap', className)}>
      {format.money(value)}
    </span>
  );
}
