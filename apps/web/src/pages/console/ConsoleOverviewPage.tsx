import { useTranslation } from 'react-i18next';

import { SessionStatus, useSession } from '@/features/auth';

/** The console start for agents and evaluators: what the role handles, and the session. */
export function ConsoleOverviewPage() {
  const { t } = useTranslation();
  const session = useSession();
  const role = session.data?.role;
  return (
    <div className="flex max-w-4xl flex-col gap-8">
      <div className="flex flex-col gap-2">
        <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
          {t('console.heading')}
        </h1>
        {role === 'agent' && (
          <p className="max-w-prose text-body text-fg-secondary">{t('console.agentBody')}</p>
        )}
        {role === 'evaluator' && (
          <p className="max-w-prose text-body text-fg-secondary">{t('console.evaluatorBody')}</p>
        )}
      </div>
      <SessionStatus />
    </div>
  );
}
