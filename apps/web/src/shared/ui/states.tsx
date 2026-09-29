import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';

import { EmptyIcon, WarningIcon, type Icon } from './icons';

interface StateProps {
  readonly title: string;
  readonly description?: ReactNode;
  readonly action?: ReactNode;
  readonly icon?: Icon;
  readonly className?: string;
}

/** Nothing to show yet: says why, and what would fill it. */
export function EmptyState({
  title,
  description,
  action,
  icon: StateIcon = EmptyIcon,
  className,
}: StateProps) {
  return (
    <div
      className={cx(
        'flex flex-col items-start gap-3 rounded-card border border-dashed border-border-strong p-6',
        className,
      )}
    >
      <StateIcon aria-hidden="true" size={28} className="text-fg-muted" />
      <div className="flex flex-col gap-1">
        <p className="text-body font-semibold text-fg">{title}</p>
        {description !== undefined && (
          <p className="max-w-prose text-small text-fg-secondary">{description}</p>
        )}
      </div>
      {action}
    </div>
  );
}

/**
 * Something failed: a plain message, the request id when there is one (support can find the log line), and a way
 * forward. Announced as an alert.
 */
export function ErrorState({
  title,
  description,
  action,
  requestId,
  icon: StateIcon = WarningIcon,
  className,
}: StateProps & { readonly requestId?: string | undefined }) {
  const { t } = useTranslation();
  return (
    <div
      role="alert"
      className={cx(
        'flex flex-col items-start gap-3 rounded-card border border-risk bg-risk-subtle p-6',
        className,
      )}
    >
      <StateIcon aria-hidden="true" size={28} className="text-risk-text" />
      <div className="flex flex-col gap-1">
        <p className="text-body font-semibold text-fg">{title}</p>
        {description !== undefined && (
          <p className="max-w-prose text-small text-fg">{description}</p>
        )}
        {requestId !== undefined && (
          <p className="text-caption text-fg-secondary">
            {t('errors.referenceId')}: <span className="font-mono">{requestId}</span>
          </p>
        )}
      </div>
      {action}
    </div>
  );
}
