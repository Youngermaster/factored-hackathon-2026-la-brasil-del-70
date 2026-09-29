import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { cx } from '@/shared/lib/cx';
import { ClockIcon } from '@/shared/ui';

import { isOverdue } from '../model/sla';

/** The SLA as text first ("due in 3 hours", "overdue, 20 minutes ago"); the risk color only repeats it. */
export function SlaText({ due, now }: { readonly due: string; readonly now: Date }) {
  const { t } = useTranslation();
  const format = useFormat();
  const overdue = isOverdue(due, now);
  return (
    <span
      className={cx(
        'inline-flex items-center gap-1.5 whitespace-nowrap',
        overdue ? 'font-semibold text-risk-text' : 'text-fg',
      )}
    >
      <ClockIcon aria-hidden="true" size={16} />
      <time dateTime={due} title={format.dateTime(due)}>
        {overdue
          ? t('inbox.overdue', { relative: format.relative(due, now) })
          : t('inbox.dueIn', { relative: format.relative(due, now) })}
      </time>
    </span>
  );
}
