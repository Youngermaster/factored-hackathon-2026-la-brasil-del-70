import type { HTMLAttributes } from 'react';

import { cx } from '@/shared/lib/cx';

/** Gaps on the spacing scale (4 px steps): 1 = 4 px, 2 = 8 px, 3 = 12 px, 4 = 16 px, 6 = 24 px, 8 = 32 px, 12 = 48 px. */
export type Gap = 1 | 2 | 3 | 4 | 6 | 8 | 12;

const gaps: Record<Gap, string> = {
  1: 'gap-1',
  2: 'gap-2',
  3: 'gap-3',
  4: 'gap-4',
  6: 'gap-6',
  8: 'gap-8',
  12: 'gap-12',
};

type Element = 'div' | 'section' | 'ul' | 'ol' | 'header' | 'footer' | 'nav';

interface LayoutProps extends HTMLAttributes<HTMLElement> {
  readonly gap?: Gap;
  readonly as?: Element;
}

/** Vertical rhythm: children in a column with one gap. */
export function Stack({ gap = 4, as: Component = 'div', className, ...props }: LayoutProps) {
  return <Component className={cx('flex flex-col', gaps[gap], className)} {...props} />;
}

/** Children in a row that wraps, vertically centered. */
export function Inline({ gap = 3, as: Component = 'div', className, ...props }: LayoutProps) {
  return (
    <Component className={cx('flex flex-wrap items-center', gaps[gap], className)} {...props} />
  );
}
