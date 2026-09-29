import type { HTMLAttributes, ReactNode } from 'react';

import { cx } from '@/shared/lib/cx';

/**
 * An ordered trace of steps (a turn's understanding, rules, tool calls, verification). The marker color carries
 * the step's meaning: `understanding` for model steps, `decision` for deterministic rules and verified actions,
 * `risk` for refusals and escalations, `neutral` for data reads. The meaning is also in the text, never color alone.
 */
export type TimelineTone = 'neutral' | 'understanding' | 'decision' | 'risk';

const markers: Record<TimelineTone, string> = {
  neutral: 'border-border-strong bg-surface',
  understanding: 'border-understanding bg-understanding',
  decision: 'border-decision-fg bg-decision',
  risk: 'border-risk bg-risk',
};

export function Root({ className, ...props }: HTMLAttributes<HTMLOListElement>) {
  return <ol className={cx('flex flex-col', className)} {...props} />;
}

export function Item({
  tone = 'neutral',
  title,
  meta,
  children,
}: {
  readonly tone?: TimelineTone;
  readonly title: ReactNode;
  /** Right-aligned detail, for example the time or the latency. */
  readonly meta?: ReactNode;
  readonly children?: ReactNode;
}) {
  return (
    <li data-tone={tone} className="relative flex gap-4 pb-6 last:pb-0">
      <span aria-hidden="true" className="relative flex w-3 shrink-0 justify-center">
        <span className="absolute top-5 bottom-[-0.25rem] w-px bg-border" />
        <span className={cx('relative mt-1.5 size-3 rounded-full border-2', markers[tone])} />
      </span>
      <div className="flex min-w-0 flex-1 flex-col gap-1">
        <div className="flex flex-wrap items-baseline justify-between gap-x-4">
          <p className="text-small font-semibold text-fg">{title}</p>
          {meta !== undefined && (
            <p className="font-mono text-caption text-fg-muted tabular-nums">{meta}</p>
          )}
        </div>
        {children !== undefined && <div className="text-small text-fg-secondary">{children}</div>}
      </div>
    </li>
  );
}
