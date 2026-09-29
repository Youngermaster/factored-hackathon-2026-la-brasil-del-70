import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { HumanIcon } from '@/shared/ui';

import { useMessage } from '../../model/message-context';
import { PartCard } from './PartCard';

/** The handoff: a reference the customer can quote and when to expect an answer. A service, not a failure. */
export function Escalation() {
  const { t } = useTranslation();
  const format = useFormat();
  const { message } = useMessage();
  const escalation = message.escalation;
  if (escalation === null || escalation === undefined) {
    return null;
  }
  return (
    <PartCard
      tone="risk"
      title={
        <span className="flex items-center gap-2">
          <HumanIcon aria-hidden="true" size={18} className="text-risk-text" />
          {t('parts.escalation.title')}
        </span>
      }
    >
      <dl className="grid grid-cols-1 gap-3 text-small sm:grid-cols-2">
        <div className="flex flex-col gap-0.5">
          <dt className="text-fg-secondary">{t('parts.escalation.reference')}</dt>
          <dd className="font-mono font-semibold break-all text-fg">{escalation.handoff_id}</dd>
        </div>
        <div className="flex flex-col gap-0.5">
          <dt className="text-fg-secondary">{t('parts.escalation.expected')}</dt>
          <dd className="text-fg">
            <time dateTime={escalation.expected_response_by}>
              {format.dateTime(escalation.expected_response_by)}
            </time>
          </dd>
        </div>
      </dl>
    </PartCard>
  );
}
