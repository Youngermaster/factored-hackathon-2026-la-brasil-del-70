import type { Ref, SelectHTMLAttributes } from 'react';

import { cx } from '@/shared/lib/cx';

import { controlClasses } from './controls';
import { CaretDownIcon } from './icons';

/**
 * A styled native <select>. Native beats a custom listbox here: the platform picker on phones, typeahead, and
 * screen reader support come for free (docs/adr/0018-design-system.md).
 */
export function Select({
  className,
  children,
  ref,
  ...props
}: SelectHTMLAttributes<HTMLSelectElement> & { readonly ref?: Ref<HTMLSelectElement> }) {
  return (
    <span className={cx('relative inline-flex w-full', className)}>
      <select ref={ref} className={cx(controlClasses, 'h-11 appearance-none pr-10')} {...props}>
        {children}
      </select>
      <CaretDownIcon
        aria-hidden="true"
        size={16}
        className="pointer-events-none absolute top-1/2 right-3 -translate-y-1/2 text-fg-secondary"
      />
    </span>
  );
}
