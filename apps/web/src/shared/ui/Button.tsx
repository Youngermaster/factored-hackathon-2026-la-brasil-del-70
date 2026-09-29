import { Slot } from 'radix-ui';
import type { ButtonHTMLAttributes, ReactNode, Ref } from 'react';

import { cx } from '@/shared/lib/cx';

import { buttonClasses, type ButtonSize, type ButtonVariant } from './button-classes';

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  readonly variant?: ButtonVariant;
  readonly size?: ButtonSize;
  /** Renders the child element (for example a router link) with the button styles. */
  readonly asChild?: boolean;
  /** Marks a running action: announced as busy and not clickable, without changing the width. */
  readonly pending?: boolean;
  readonly children: ReactNode;
  readonly ref?: Ref<HTMLButtonElement>;
}

export function Button({
  variant = 'primary',
  size = 'md',
  asChild = false,
  pending = false,
  className,
  type,
  onClick,
  ...props
}: ButtonProps) {
  const Component = asChild ? Slot.Root : 'button';
  return (
    <Component
      className={cx(buttonClasses(variant, size), className)}
      {...(asChild ? {} : { type: type ?? 'button' })}
      aria-busy={pending || undefined}
      aria-disabled={pending || undefined}
      onClick={
        pending
          ? (event) => {
              event.preventDefault();
            }
          : onClick
      }
      {...props}
    />
  );
}
