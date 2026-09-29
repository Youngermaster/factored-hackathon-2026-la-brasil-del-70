import { Tabs as RadixTabs } from 'radix-ui';
import type { ComponentProps } from 'react';

import { cx } from '@/shared/lib/cx';

/** Tabs on Radix: arrow keys move between tabs, Tab moves into the panel. */
export function List({ className, ...props }: ComponentProps<typeof RadixTabs.List>) {
  return (
    <RadixTabs.List className={cx('flex gap-1 border-b border-border', className)} {...props} />
  );
}

export function Trigger({ className, ...props }: ComponentProps<typeof RadixTabs.Trigger>) {
  return (
    <RadixTabs.Trigger
      className={cx(
        '-mb-px inline-flex h-10 items-center gap-2 border-b-2 border-transparent px-3 text-small font-medium',
        'text-fg-secondary hover:text-fg data-[state=active]:border-fg data-[state=active]:text-fg',
        className,
      )}
      {...props}
    />
  );
}

export function Panel({ className, ...props }: ComponentProps<typeof RadixTabs.Content>) {
  return <RadixTabs.Content className={cx('pt-5', className)} {...props} />;
}

export function Root(props: ComponentProps<typeof RadixTabs.Root>) {
  return <RadixTabs.Root {...props} />;
}
