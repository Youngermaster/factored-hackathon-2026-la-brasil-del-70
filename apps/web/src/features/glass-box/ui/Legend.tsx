import { useTranslation } from 'react-i18next';

import { cx } from '@/shared/lib/cx';
import { InfoIcon } from '@/shared/ui';

/**
 * The fixed note (no model reasoning is shown, by design) and the color legend. The legend repeats in words what
 * each marker color means, so the trace never relies on color alone.
 */
export function Legend() {
  const { t } = useTranslation();
  const items = [
    { marker: 'bg-understanding', text: t('glass.legend.understanding') },
    { marker: 'bg-decision', text: t('glass.legend.decision') },
    { marker: 'bg-risk', text: t('glass.legend.risk') },
  ];
  return (
    <div className="flex flex-col gap-3">
      <p className="flex items-start gap-2 rounded-card border border-border bg-surface-sunken p-3 text-small text-fg">
        <InfoIcon aria-hidden="true" size={18} className="mt-0.5 shrink-0" />
        {t('glass.reasoningNote')}
      </p>
      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-caption text-fg-secondary">
        {items.map(({ marker, text }) => (
          <li key={marker} className="flex items-center gap-1.5">
            <span aria-hidden="true" className={cx('size-2.5 rounded-full', marker)} />
            {text}
          </li>
        ))}
      </ul>
    </div>
  );
}
