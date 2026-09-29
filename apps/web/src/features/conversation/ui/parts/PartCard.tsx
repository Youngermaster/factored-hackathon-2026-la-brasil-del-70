import { useId, type ReactNode } from 'react';

import { cx } from '@/shared/lib/cx';

/**
 * The frame of one structured part inside an assistant message: a titled region on a surface, so a screen reader
 * can jump between parts. `tone` follows the color meanings: risk for escalations, neutral for everything else.
 */
export function PartCard({
  title,
  meta,
  tone = 'neutral',
  children,
  className,
}: {
  readonly title: ReactNode;
  readonly meta?: ReactNode;
  readonly tone?: 'neutral' | 'risk';
  readonly children: ReactNode;
  readonly className?: string;
}) {
  const id = useId();
  return (
    <section
      aria-labelledby={id}
      className={cx(
        'flex flex-col gap-3 rounded-card border p-4',
        tone === 'risk' ? 'border-risk bg-risk-subtle' : 'border-border bg-surface',
        className,
      )}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <h3 id={id} className="text-small font-semibold text-fg">
          {title}
        </h3>
        {meta}
      </div>
      {children}
    </section>
  );
}
