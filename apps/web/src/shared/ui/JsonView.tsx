import { cx } from '@/shared/lib/cx';

/**
 * Read-only structured data (a handoff payload, an execution record) as indented JSON text. The value is
 * serialized and rendered as a text node, so markup inside strings is shown, never interpreted.
 */
export function JsonView({
  value,
  label,
  className,
}: {
  readonly value: unknown;
  /** Names the scrollable region for assistive technology. */
  readonly label: string;
  readonly className?: string;
}) {
  const text = value === undefined ? 'undefined' : JSON.stringify(value, null, 2);
  return (
    <pre
      role="region"
      aria-label={label}
      // Keyboard users can scroll long records (WCAG 2.1.1).
      tabIndex={0}
      className={cx(
        'max-h-96 overflow-auto rounded-card border border-border bg-surface-sunken p-4',
        'font-mono text-caption leading-relaxed text-fg whitespace-pre',
        className,
      )}
    >
      {text}
    </pre>
  );
}
