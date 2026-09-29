import type { ButtonHTMLAttributes, ReactElement, Ref } from 'react';

import { cx } from '@/shared/lib/cx';

import { buttonClasses, type ButtonVariant } from './button-classes';

export interface IconButtonProps extends Omit<
  ButtonHTMLAttributes<HTMLButtonElement>,
  'children' | 'aria-label'
> {
  /** The accessible name; an icon alone has none. */
  readonly label: string;
  readonly icon: ReactElement;
  readonly variant?: Exclude<ButtonVariant, 'danger'>;
  readonly ref?: Ref<HTMLButtonElement>;
}

/** A square button with an icon and a required accessible name. Pair it with <Tooltip> when sighted users need the label. */
export function IconButton({
  label,
  icon,
  variant = 'ghost',
  className,
  type,
  ...props
}: IconButtonProps) {
  return (
    <button
      type={type ?? 'button'}
      aria-label={label}
      className={cx(buttonClasses(variant, 'md'), 'w-10 px-0', className)}
      {...props}
    >
      <span aria-hidden="true" className="inline-flex">
        {icon}
      </span>
    </button>
  );
}
