import { Slot } from 'radix-ui';
import type { AnchorHTMLAttributes, ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';

import { ExternalIcon } from './icons';

export interface TextLinkProps extends AnchorHTMLAttributes<HTMLAnchorElement> {
  /** Renders the child (for example a router <Link>) with the link styles. */
  readonly asChild?: boolean;
  /** Opens in a new tab with `rel="noopener noreferrer"` and says so to screen readers. */
  readonly external?: boolean;
  readonly children: ReactNode;
}

const linkClasses =
  'font-medium text-fg underline decoration-border-strong underline-offset-4 hover:decoration-fg';

/** An inline text link. Internal routes pass a router link as the child; external links set `external`. */
export function TextLink({
  asChild = false,
  external = false,
  className,
  children,
  ...props
}: TextLinkProps) {
  const { t } = useTranslation();
  if (asChild) {
    return (
      <Slot.Root className={cx(linkClasses, className)} {...props}>
        {children}
      </Slot.Root>
    );
  }
  return (
    <a
      className={cx(linkClasses, 'inline-flex items-center gap-1', className)}
      {...(external ? { target: '_blank', rel: 'noopener noreferrer' } : {})}
      {...props}
    >
      {children}
      {external && (
        <>
          <ExternalIcon aria-hidden="true" size={16} />
          <span className="sr-only">{t('common.opensInNewTab')}</span>
        </>
      )}
    </a>
  );
}
