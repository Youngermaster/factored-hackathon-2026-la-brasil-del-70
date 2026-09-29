import { useTranslation } from 'react-i18next';

import { CreditApplicationList } from '@/features/agent-inbox';
import { RequireSession } from '@/features/auth';

/** Credit intakes recorded for human review, read only. */
export function CreditApplicationsPage() {
  const { t } = useTranslation();
  return (
    <RequireSession roles={['agent']}>
      <div className="flex flex-col gap-6">
        <div className="flex max-w-3xl flex-col gap-2">
          <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
            {t('applications.heading')}
          </h1>
          <p className="text-body text-fg-secondary">{t('applications.intro')}</p>
        </div>
        <CreditApplicationList />
      </div>
    </RequireSession>
  );
}
