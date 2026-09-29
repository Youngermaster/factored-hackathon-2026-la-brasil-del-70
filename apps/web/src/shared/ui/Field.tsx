import { Slot } from 'radix-ui';
import {
  useId,
  useMemo,
  type HTMLAttributes,
  type LabelHTMLAttributes,
  type ReactNode,
} from 'react';

import { cx } from '@/shared/lib/cx';

import { FieldContext, useField } from './field-context';
import { WarningIcon } from './icons';

interface RootProps {
  /** Shows <Field.Error> and marks the control `aria-invalid`. */
  readonly invalid?: boolean;
  readonly required?: boolean;
  /** Renders <Field.Hint>; the control is described by it. */
  readonly hasHint?: boolean;
  readonly className?: string;
  readonly children: ReactNode;
}

export function Root({
  invalid = false,
  required = false,
  hasHint = false,
  className,
  children,
}: RootProps) {
  const id = useId();
  const value = useMemo(() => {
    const hintId = `${id}-hint`;
    const errorId = `${id}-error`;
    const describedBy = [hasHint ? hintId : null, invalid ? errorId : null]
      .filter(Boolean)
      .join(' ');
    return {
      controlId: `${id}-control`,
      hintId,
      errorId,
      invalid,
      required,
      describedBy: describedBy === '' ? undefined : describedBy,
    };
  }, [id, invalid, required, hasHint]);
  return (
    <FieldContext value={value}>
      <div className={cx('flex flex-col gap-2', className)}>{children}</div>
    </FieldContext>
  );
}

function useRequiredField(part: string) {
  const field = useField();
  if (field === null) {
    throw new Error(`<Field.${part}> must be inside <Field.Root>`);
  }
  return field;
}

export function Label({ className, children, ...props }: LabelHTMLAttributes<HTMLLabelElement>) {
  const field = useRequiredField('Label');
  return (
    <label
      htmlFor={field.controlId}
      className={cx('text-small font-medium text-fg', className)}
      {...props}
    >
      {children}
    </label>
  );
}

/** Passes the field's id, description, and validity to its single child control. */
export function Control({ children }: { readonly children: ReactNode }) {
  const field = useRequiredField('Control');
  return (
    <Slot.Root
      id={field.controlId}
      aria-describedby={field.describedBy}
      aria-invalid={field.invalid || undefined}
      aria-required={field.required || undefined}
    >
      {children}
    </Slot.Root>
  );
}

export function Hint({ className, ...props }: HTMLAttributes<HTMLParagraphElement>) {
  const field = useRequiredField('Hint');
  return <p id={field.hintId} className={cx('text-small text-fg-muted', className)} {...props} />;
}

export function ErrorMessage({
  className,
  children,
  ...props
}: HTMLAttributes<HTMLParagraphElement>) {
  const field = useRequiredField('Error');
  if (!field.invalid) {
    return null;
  }
  return (
    <p
      id={field.errorId}
      className={cx('flex items-start gap-1.5 text-small font-medium text-risk-text', className)}
      {...props}
    >
      <WarningIcon aria-hidden="true" size={18} className="mt-px shrink-0" />
      <span>{children}</span>
    </p>
  );
}

/** A form field: label above, control, hint, and error below, wired with ids and ARIA. */

export { ErrorMessage as Error };
