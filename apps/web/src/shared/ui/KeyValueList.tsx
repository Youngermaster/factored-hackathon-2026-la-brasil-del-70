import type { HTMLAttributes, ReactNode } from 'react';

import { cx } from '@/shared/lib/cx';

/** Label and value pairs as a description list. `columns` lays items out in a grid on wide screens. */
export function Root({
  columns = 1,
  className,
  ...props
}: HTMLAttributes<HTMLDListElement> & { readonly columns?: 1 | 2 | 3 }) {
  const grid = { 1: '', 2: 'sm:grid-cols-2', 3: 'sm:grid-cols-2 lg:grid-cols-3' }[columns];
  return <dl className={cx('grid grid-cols-1 gap-x-8 gap-y-4', grid, className)} {...props} />;
}

export function Item({
  label,
  children,
  numeric = false,
}: {
  readonly label: ReactNode;
  readonly children: ReactNode;
  /** Amounts and counts: monospaced tabular figures. */
  readonly numeric?: boolean;
}) {
  return (
    <div className="flex min-w-0 flex-col gap-1">
      <dt className="text-small text-fg-muted">{label}</dt>
      <dd className={cx('text-body text-fg break-words', numeric && 'font-mono tabular-nums')}>
        {children}
      </dd>
    </div>
  );
}
