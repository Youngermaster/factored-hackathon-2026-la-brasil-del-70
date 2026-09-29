import { useTranslation } from 'react-i18next';

import { HandoffFilters, HandoffList } from '@/features/agent-inbox';
import { RequireSession } from '@/features/auth';

/** The agent's handoff inbox: filters over the list. */
export function AgentInboxPage() {
  const { t } = useTranslation();
  return (
    <RequireSession roles={['agent']}>
      <div className="flex flex-col gap-6">
        <div className="flex max-w-3xl flex-col gap-2">
          <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
            {t('inbox.heading')}
          </h1>
          <p className="text-body text-fg-secondary">{t('inbox.intro')}</p>
        </div>
        <HandoffFilters />
        <HandoffList />
      </div>
    </RequireSession>
  );
}
