import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import { isDemoMode } from '@/shared/config';
import { Badge } from '@/shared/ui';

/** The product name in the deck's display face, and the demo-mode label whenever demo mode is on. */
export function Wordmark({ to }: { readonly to: string }) {
  const { t } = useTranslation();
  return (
    <div className="flex min-w-0 items-center gap-3">
      <Link
        to={to}
        className="rounded-control font-display text-body font-semibold tracking-tight text-fg"
      >
        {t('app.name')}
      </Link>
      {isDemoMode() && <Badge title={t('app.demoModeHint')}>{t('app.demoMode')}</Badge>}
    </div>
  );
}
