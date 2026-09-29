import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';

/** A placeholder block shaped like the content it stands for. Hidden from assistive technology. */
export function Skeleton({ className }: { readonly className?: string }) {
  return (
    <span
      aria-hidden="true"
      className={cx('block rounded-control bg-surface-sunken animate-skeleton', className)}
    />
  );
}

/** Wraps skeletons in a status region that announces "Loading" once. */
export function SkeletonGroup({
  children,
  className,
  label,
}: {
  readonly children: ReactNode;
  readonly className?: string;
  readonly label?: string;
}) {
  const { t } = useTranslation();
  return (
    <div role="status" aria-busy="true" className={cx('flex flex-col gap-3', className)}>
      <span className="sr-only">{label ?? t('common.loading')}</span>
      {children}
    </div>
  );
}
