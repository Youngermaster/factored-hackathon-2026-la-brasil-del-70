import type { ReactNode } from 'react';

/** A titled section of the supervision view; the heading names the region for assistive technology. */
export function Section({
  id,
  title,
  intro,
  aside,
  children,
}: {
  readonly id: string;
  readonly title: string;
  readonly intro?: ReactNode;
  readonly aside?: ReactNode;
  readonly children: ReactNode;
}) {
  return (
    <section aria-labelledby={id} className="flex flex-col gap-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div className="flex max-w-3xl flex-col gap-1">
          <h2 id={id} className="text-title font-semibold text-fg">
            {title}
          </h2>
          {intro !== undefined && <p className="text-small text-fg-secondary">{intro}</p>}
        </div>
        {aside}
      </div>
      {children}
    </section>
  );
}
