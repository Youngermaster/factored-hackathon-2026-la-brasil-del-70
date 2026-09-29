import {
  useId,
  type HTMLAttributes,
  type ReactNode,
  type TdHTMLAttributes,
  type ThHTMLAttributes,
} from 'react';
import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';

import { CaretDownIcon, CaretUpIcon, SortIcon } from './icons';

export type SortDirection = 'ascending' | 'descending';

/** A data table with a required caption (its accessible name). Wide tables scroll inside a focusable region. */
export function Root({
  caption,
  captionHidden = false,
  className,
  children,
}: {
  readonly caption: ReactNode;
  /** Keeps the caption for screen readers when a visible heading already names the table. */
  readonly captionHidden?: boolean;
  readonly className?: string;
  readonly children: ReactNode;
}) {
  const captionId = useId();
  return (
    <div
      // Keyboard users can scroll a wide table (WCAG 2.1.1); the region is named by the table caption.
      role="region"
      aria-labelledby={captionId}
      tabIndex={0}
      className={cx('overflow-x-auto rounded-card border border-border bg-surface', className)}
    >
      <table className="w-full border-collapse text-left text-small">
        <caption
          className={cx(
            'px-4 pt-4 pb-2 text-left text-small font-semibold text-fg',
            captionHidden && 'sr-only',
          )}
        >
          {caption}
        </caption>
        {children}
      </table>
    </div>
  );
}

export function Head(props: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead className="border-b border-border" {...props} />;
}

export function Body(props: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody className="divide-y divide-border" {...props} />;
}

export function Row({ className, ...props }: HTMLAttributes<HTMLTableRowElement>) {
  return <tr className={cx('hover:bg-surface-hover', className)} {...props} />;
}

interface HeaderCellProps extends ThHTMLAttributes<HTMLTableCellElement> {
  readonly numeric?: boolean;
  /** Present when the column sorts: the current direction, or null when another column sorts. */
  readonly sort?: SortDirection | null;
  readonly onSort?: () => void;
}

export function HeaderCell({
  numeric = false,
  sort,
  onSort,
  className,
  children,
  ...props
}: HeaderCellProps) {
  const { t } = useTranslation();
  const sortable = onSort !== undefined;
  const Indicator =
    sort === 'ascending' ? CaretUpIcon : sort === 'descending' ? CaretDownIcon : SortIcon;
  return (
    <th
      scope="col"
      aria-sort={sortable ? (sort ?? 'none') : undefined}
      className={cx('px-4 py-3 font-medium text-fg-secondary', numeric && 'text-right', className)}
      {...props}
    >
      {sortable ? (
        <button
          type="button"
          onClick={onSort}
          className={cx(
            'inline-flex items-center gap-1 rounded-control hover:text-fg',
            numeric && 'flex-row-reverse',
          )}
        >
          {children}
          <Indicator aria-hidden="true" size={14} />
          <span className="sr-only">
            {sort === 'ascending'
              ? t('data.sortedAscending')
              : sort === 'descending'
                ? t('data.sortedDescending')
                : ''}
          </span>
        </button>
      ) : (
        children
      )}
    </th>
  );
}

export function Cell({
  numeric = false,
  className,
  ...props
}: TdHTMLAttributes<HTMLTableCellElement> & { readonly numeric?: boolean }) {
  return (
    <td
      className={cx(
        'px-4 py-3 align-top text-fg',
        numeric && 'text-right font-mono tabular-nums',
        className,
      )}
      {...props}
    />
  );
}
