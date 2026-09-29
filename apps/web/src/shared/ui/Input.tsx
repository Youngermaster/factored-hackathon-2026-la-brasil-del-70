import type { InputHTMLAttributes, Ref, TextareaHTMLAttributes } from 'react';

import { cx } from '@/shared/lib/cx';

import { controlClasses } from './controls';

export function Input({
  className,
  ref,
  ...props
}: InputHTMLAttributes<HTMLInputElement> & { readonly ref?: Ref<HTMLInputElement> }) {
  return <input ref={ref} className={cx(controlClasses, 'h-11', className)} {...props} />;
}

export function Textarea({
  className,
  ref,
  compact = false,
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & {
  readonly ref?: Ref<HTMLTextAreaElement>;
  /** A short box that grows with its rows (the chat composer) instead of the default minimum height. */
  readonly compact?: boolean;
}) {
  return (
    <textarea
      ref={ref}
      className={cx(
        controlClasses,
        compact ? 'py-2.5' : 'min-h-24 py-2',
        'leading-relaxed',
        className,
      )}
      {...props}
    />
  );
}
