import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';

import { CheckIcon, ClockIcon, FailedIcon, HumanIcon, ReviewIcon, type Icon } from './icons';

export type Status = 'verified' | 'pending' | 'failed' | 'escalated' | 'review_required';

/**
 * Only `verified` gets the yellow fill: it is reserved for actions whose outcome the system read back. A review or
 * an eligibility indication is never styled as success (docs/design/DESIGN.md, data display rules).
 */
type StatusLabel =
  | 'status.verified'
  | 'status.pending'
  | 'status.failed'
  | 'status.escalated'
  | 'status.reviewRequired';

const styles: Record<Status, { classes: string; icon: Icon; label: StatusLabel }> = {
  verified: { classes: 'bg-decision text-decision-fg', icon: CheckIcon, label: 'status.verified' },
  pending: {
    classes: 'bg-surface-sunken text-fg-secondary',
    icon: ClockIcon,
    label: 'status.pending',
  },
  failed: { classes: 'bg-risk-subtle text-risk-text', icon: FailedIcon, label: 'status.failed' },
  escalated: {
    classes: 'bg-risk-subtle text-risk-text',
    icon: HumanIcon,
    label: 'status.escalated',
  },
  review_required: {
    classes: 'border border-border-strong bg-surface text-fg',
    icon: ReviewIcon,
    label: 'status.reviewRequired',
  },
};

export function StatusPill({
  status,
  className,
}: {
  readonly status: Status;
  readonly className?: string;
}) {
  const { t } = useTranslation();
  const { classes, icon: StatusIcon, label } = styles[status];
  return (
    <span
      data-status={status}
      className={cx(
        'inline-flex h-7 items-center gap-1.5 rounded-full px-3 text-caption font-semibold whitespace-nowrap',
        classes,
        className,
      )}
    >
      <StatusIcon aria-hidden="true" size={16} />
      {t(label)}
    </span>
  );
}
