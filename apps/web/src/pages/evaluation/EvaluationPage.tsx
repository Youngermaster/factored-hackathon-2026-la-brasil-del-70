import { useTranslation } from 'react-i18next';

import { RequireSession } from '@/features/auth';
import { EvaluationReport } from '@/features/eval-report';

/** The evaluator's view of the published evaluation summaries. */
export function EvaluationPage() {
  const { t } = useTranslation();
  return (
    <RequireSession roles={['evaluator']}>
      <div className="flex flex-col gap-6">
        <div className="flex max-w-3xl flex-col gap-2">
          <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
            {t('eval.heading')}
          </h1>
          <p className="text-body text-fg-secondary">{t('eval.intro')}</p>
        </div>
        <EvaluationReport />
      </div>
    </RequireSession>
  );
}
