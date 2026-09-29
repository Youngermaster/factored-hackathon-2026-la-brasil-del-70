import { useState, type ChangeEvent, type InputHTMLAttributes, type Ref } from 'react';

import { cx } from '@/shared/lib/cx';

export interface OneTimeCodeInputProps extends Omit<
  InputHTMLAttributes<HTMLInputElement>,
  'value' | 'onChange' | 'maxLength' | 'type'
> {
  readonly value: string;
  readonly onValueChange: (value: string) => void;
  /** Called once the code has all its digits (typed, pasted, or autofilled). */
  readonly onComplete?: (value: string) => void;
  readonly length?: number;
  readonly ref?: Ref<HTMLInputElement>;
}

/**
 * One real text field for a one-time code, drawn as digit boxes. A single field keeps what separate boxes break:
 * paste, SMS autofill (`autocomplete="one-time-code"`), native backspace and selection, and one label for screen
 * readers. The boxes are presentation only (`aria-hidden`); the input sits on top of them, transparent.
 */
export function OneTimeCodeInput({
  value,
  onValueChange,
  onComplete,
  length = 6,
  className,
  disabled,
  ref,
  onFocus,
  onBlur,
  ...props
}: OneTimeCodeInputProps) {
  const [focused, setFocused] = useState(false);

  const handleChange = (event: ChangeEvent<HTMLInputElement>) => {
    // Pasted codes often carry spaces or dashes ("123 456", "123-456"); keep the digits only.
    const digits = event.target.value.replace(/\D/g, '').slice(0, length);
    onValueChange(digits);
    if (digits.length === length && digits !== value) {
      onComplete?.(digits);
    }
  };

  const active = Math.min(value.length, length - 1);

  return (
    <div className={cx('relative inline-flex w-full max-w-sm', className)}>
      <div aria-hidden="true" className="grid w-full grid-cols-6 gap-2">
        {Array.from({ length }, (_, index) => (
          <span
            key={index}
            className={cx(
              'flex h-14 items-center justify-center rounded-control border bg-surface font-mono text-heading text-fg tabular-nums',
              focused && index === active && !disabled
                ? 'border-fg outline-2 outline-offset-2 outline-focus'
                : 'border-border-strong',
              disabled && 'opacity-60',
            )}
          >
            {value[index] ?? ''}
          </span>
        ))}
      </div>
      <input
        ref={ref}
        type="text"
        inputMode="numeric"
        autoComplete="one-time-code"
        pattern="[0-9]*"
        maxLength={length + 8}
        spellCheck={false}
        value={value}
        disabled={disabled}
        onChange={handleChange}
        onFocus={(event) => {
          setFocused(true);
          onFocus?.(event);
        }}
        onBlur={(event) => {
          setFocused(false);
          onBlur?.(event);
        }}
        className="absolute inset-0 h-full w-full cursor-text bg-transparent text-transparent caret-transparent outline-none selection:bg-transparent"
        {...props}
      />
    </div>
  );
}
