import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n/context';
import { cx } from '@/shared/lib/cx';

import { ClockIcon } from './icons';

/**
 * The as-of instant of snapshot data, such as a balance. Every balance shows one: the data is a snapshot, not a
 * live ledger.
 */
export function AsOfNote({ at, className }: { readonly at: string; readonly className?: string }) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <p className={cx('inline-flex items-center gap-1.5 text-small text-fg-muted', className)}>
      <ClockIcon aria-hidden="true" size={16} />
      <time dateTime={at}>{t('data.asOf', { date: format.dateTime(at) })}</time>
    </p>
  );
}
