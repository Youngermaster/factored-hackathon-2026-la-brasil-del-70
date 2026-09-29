import { useTranslation } from 'react-i18next';

import { useStaffTrace } from '../api/trace';
import { Legend } from './Legend';
import { TraceBody } from './TraceBody';

/**
 * The evaluator's glass box: the same record as the customer's, plus what customers never see (the estimate
 * values, the risk tier, trust events, and safety interventions), each in its own labeled region.
 */
export function StaffTrace({ conversationId }: { readonly conversationId: string }) {
  const { t } = useTranslation();
  const trace = useStaffTrace(conversationId);
  return (
    <div className="flex flex-col gap-4">
      <p className="text-small text-fg-muted">
        {t('chat.reference')} <span className="font-mono">{conversationId}</span>
      </p>
      <Legend />
      <TraceBody query={trace} view="staff" />
    </div>
  );
}
