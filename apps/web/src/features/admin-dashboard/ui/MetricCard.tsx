import type { ReactNode } from 'react';

import { cx } from '@/shared/lib/cx';

export function MetricCard({
  label,
  value,
  detail,
  tone = 'neutral',
}: {
  readonly label: ReactNode;
  readonly value: ReactNode;
  readonly detail: ReactNode;
  readonly tone?: 'neutral' | 'decision' | 'risk' | 'understanding';
}) {
  const marker = {
    neutral: 'bg-border-strong',
    decision: 'bg-decision',
    risk: 'bg-risk',
    understanding: 'bg-understanding',
  }[tone];
  return (
    <section className="flex min-h-36 flex-col justify-between rounded-card border border-border bg-surface p-5">
      <div className="flex items-center gap-2 text-caption font-medium text-fg-secondary">
        <span aria-hidden="true" className={cx('h-2 w-2 rounded-full', marker)} />
        {label}
      </div>
      <div className="mt-5 font-display text-[2rem] leading-none font-semibold tracking-tight text-fg tabular-nums">
        {value}
      </div>
      <div className="mt-2 text-caption text-fg-muted">{detail}</div>
    </section>
  );
}
