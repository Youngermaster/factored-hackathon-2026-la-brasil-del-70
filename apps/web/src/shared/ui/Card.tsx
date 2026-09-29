import type { HTMLAttributes, ReactNode } from 'react';

import { cx } from '@/shared/lib/cx';

/** A bordered surface for a real group (a session, a balance, a handoff). Prefer spacing when no grouping is needed. */
export function Root({ className, ...props }: HTMLAttributes<HTMLElement>) {
  return (
    <section
      className={cx('flex flex-col rounded-card border border-border bg-surface', className)}
      {...props}
    />
  );
}

export function Header({
  title,
  description,
  action,
  className,
}: {
  readonly title: ReactNode;
  readonly description?: ReactNode;
  readonly action?: ReactNode;
  readonly className?: string;
}) {
  return (
    <div
      className={cx('flex items-start justify-between gap-4 px-5 pt-5 sm:px-6 sm:pt-6', className)}
    >
      <div className="flex min-w-0 flex-col gap-1">
        <h2 className="text-title font-semibold text-fg">{title}</h2>
        {description !== undefined && <p className="text-small text-fg-secondary">{description}</p>}
      </div>
      {action}
    </div>
  );
}

export function Body({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cx('px-5 py-5 sm:px-6', className)} {...props} />;
}

export function Footer({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx(
        'flex flex-wrap items-center gap-3 border-t border-border px-5 py-4 sm:px-6',
        className,
      )}
      {...props}
    />
  );
}
