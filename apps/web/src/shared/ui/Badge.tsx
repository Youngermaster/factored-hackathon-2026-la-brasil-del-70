import type { HTMLAttributes } from 'react';

import { cx } from '@/shared/lib/cx';

/** Tones follow the color meanings; `neutral` is the default and the right choice for most labels. */
export type BadgeTone = 'neutral' | 'understanding' | 'decision' | 'risk';

const tones: Record<BadgeTone, string> = {
  neutral: 'border-border-strong bg-surface text-fg-secondary',
  understanding: 'border-transparent bg-understanding-subtle text-understanding-text',
  decision: 'border-transparent bg-decision-subtle text-decision-text',
  risk: 'border-transparent bg-risk-subtle text-risk-text',
};

export function Badge({
  tone = 'neutral',
  className,
  ...props
}: HTMLAttributes<HTMLSpanElement> & { readonly tone?: BadgeTone }) {
  return (
    <span
      className={cx(
        'inline-flex h-6 items-center gap-1 rounded-control border px-2 text-caption font-medium whitespace-nowrap',
        tones[tone],
        className,
      )}
      {...props}
    />
  );
}
