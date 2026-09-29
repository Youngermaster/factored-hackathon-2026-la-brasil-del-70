import { cx } from '@/shared/lib/cx';

export type ButtonVariant = 'primary' | 'secondary' | 'ghost' | 'danger';
export type ButtonSize = 'sm' | 'md' | 'lg';

const base =
  'inline-flex shrink-0 select-none items-center justify-center gap-2 whitespace-nowrap rounded-control font-medium ' +
  'transition-[background-color,border-color,transform] duration-150 ease-(--ease-standard) ' +
  'active:translate-y-px disabled:pointer-events-none disabled:opacity-50 aria-disabled:opacity-60';

const variants: Record<ButtonVariant, string> = {
  primary: 'bg-action text-action-fg hover:bg-action-hover',
  secondary: 'border border-border-strong bg-surface text-fg hover:bg-surface-hover',
  ghost: 'text-fg hover:bg-surface-hover',
  danger: 'bg-risk text-risk-fg hover:opacity-90',
};

const sizes: Record<ButtonSize, string> = {
  sm: 'h-8 px-3 text-small',
  md: 'h-10 px-4 text-small',
  lg: 'h-12 px-5 text-body',
};

export function buttonClasses(variant: ButtonVariant = 'primary', size: ButtonSize = 'md'): string {
  return cx(base, variants[variant], sizes[size]);
}
