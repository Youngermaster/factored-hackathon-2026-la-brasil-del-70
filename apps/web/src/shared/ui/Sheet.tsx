import { Dialog as RadixDialog } from 'radix-ui';
import type { ComponentProps } from 'react';
import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';

import { CloseIcon } from './icons';

/** A side panel with the dialog's focus management: the mobile menu and, later, the glass box on narrow screens. */
export function Content({
  className,
  children,
  ...props
}: ComponentProps<typeof RadixDialog.Content>) {
  const { t } = useTranslation();
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay className="fixed inset-0 z-40 bg-overlay animate-overlay-in" />
      <RadixDialog.Content
        className={cx(
          'fixed inset-y-0 right-0 z-50 flex w-[min(24rem,100vw)] flex-col gap-6 overflow-y-auto',
          'border-l border-border bg-surface p-6 text-fg animate-sheet-in',
          className,
        )}
        {...props}
      >
        {children}
        <RadixDialog.Close
          aria-label={t('common.close')}
          className="absolute top-4 right-4 inline-flex size-9 items-center justify-center rounded-control text-fg-secondary hover:bg-surface-hover hover:text-fg"
        >
          <CloseIcon aria-hidden="true" size={20} />
        </RadixDialog.Close>
      </RadixDialog.Content>
    </RadixDialog.Portal>
  );
}

export function Title({ className, ...props }: ComponentProps<typeof RadixDialog.Title>) {
  return (
    <RadixDialog.Title className={cx('pr-10 text-title font-semibold', className)} {...props} />
  );
}

export function Root(props: ComponentProps<typeof RadixDialog.Root>) {
  return <RadixDialog.Root {...props} />;
}

export function Trigger(props: ComponentProps<typeof RadixDialog.Trigger>) {
  return <RadixDialog.Trigger {...props} />;
}

export function Close(props: ComponentProps<typeof RadixDialog.Close>) {
  return <RadixDialog.Close {...props} />;
}

export function Description(props: ComponentProps<typeof RadixDialog.Description>) {
  return <RadixDialog.Description {...props} />;
}
