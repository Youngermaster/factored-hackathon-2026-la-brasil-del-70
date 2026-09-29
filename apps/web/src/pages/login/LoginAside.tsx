import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';

/**
 * The product thesis in the deck's color meanings, on wide screens only: blue understands, yellow decides and
 * verifies, red hands over to a person. The markers repeat meaning the text already states.
 */
export function LoginAside() {
  const { t } = useTranslation();
  const rows = [
    { marker: 'bg-understanding', text: t('auth.thesisUnderstand') },
    { marker: 'bg-decision', text: t('auth.thesisDecide') },
    { marker: 'bg-risk', text: t('auth.thesisEscalate') },
  ];
  return (
    <aside
      aria-labelledby="login-aside-title"
      className="hidden self-start rounded-card border border-border bg-surface p-8 lg:block"
    >
      <h2 id="login-aside-title" className="text-small font-semibold text-fg-secondary">
        {t('auth.thesisTitle')}
      </h2>
      <ul className="mt-6 flex flex-col gap-6">
        {rows.map(({ marker, text }) => (
          <li key={marker} className="flex gap-4">
            <span
              aria-hidden="true"
              className={cx('mt-1 h-10 w-1.5 shrink-0 rounded-full', marker)}
            />
            <p className="text-body text-fg">{text}</p>
          </li>
        ))}
      </ul>
    </aside>
  );
}
