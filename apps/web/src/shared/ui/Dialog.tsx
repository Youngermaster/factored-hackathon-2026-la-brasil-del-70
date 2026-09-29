import { Dialog as RadixDialog } from 'radix-ui';
import type { ComponentProps, HTMLAttributes, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';

import { CloseIcon } from './icons';

/**
 * Modal dialog on Radix: focus moves in and is trapped, Escape closes, focus returns to the trigger, and the rest
 * of the page is inert. Every dialog needs a <Dialog.Title>; <Dialog.Description> is read on open.
 */
export function Content({
  className,
  children,
  hideClose = false,
  ...props
}: ComponentProps<typeof RadixDialog.Content> & { readonly hideClose?: boolean }) {
  const { t } = useTranslation();
  return (
    <RadixDialog.Portal>
      <RadixDialog.Overlay className="fixed inset-0 z-40 bg-overlay animate-overlay-in" />
      <RadixDialog.Content
        className={cx(
          'fixed top-1/2 left-1/2 z-50 flex max-h-[calc(100dvh-2rem)] w-[calc(100vw-2rem)] max-w-md',
          '-translate-x-1/2 -translate-y-1/2 flex-col gap-5 overflow-y-auto rounded-card border border-border',
          'bg-surface p-6 text-fg animate-panel-in',
          className,
        )}
        {...props}
      >
        {children}
        {!hideClose && (
          <RadixDialog.Close
            aria-label={t('common.close')}
            className="absolute top-4 right-4 inline-flex size-9 items-center justify-center rounded-control text-fg-secondary hover:bg-surface-hover hover:text-fg"
          >
            <CloseIcon aria-hidden="true" size={20} />
          </RadixDialog.Close>
        )}
      </RadixDialog.Content>
    </RadixDialog.Portal>
  );
}

export function Title({ className, ...props }: ComponentProps<typeof RadixDialog.Title>) {
  return (
    <RadixDialog.Title
      className={cx('pr-10 text-title font-semibold text-fg', className)}
      {...props}
    />
  );
}

export function Description({
  className,
  ...props
}: ComponentProps<typeof RadixDialog.Description>) {
  return (
    <RadixDialog.Description className={cx('text-body text-fg-secondary', className)} {...props} />
  );
}

export function Footer({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return (
    <div
      className={cx('flex flex-col-reverse gap-3 sm:flex-row sm:justify-end', className)}
      {...props}
    />
  );
}

export function Header({ children }: { readonly children: ReactNode }) {
  return <div className="flex flex-col gap-2">{children}</div>;
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
