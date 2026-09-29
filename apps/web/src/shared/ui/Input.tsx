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
  ...props
}: TextareaHTMLAttributes<HTMLTextAreaElement> & { readonly ref?: Ref<HTMLTextAreaElement> }) {
  return (
    <textarea
      ref={ref}
      className={cx(controlClasses, 'min-h-24 py-2 leading-relaxed', className)}
      {...props}
    />
  );
}
