import { useTranslation } from 'react-i18next';

import { StatusPill } from '@/shared/ui';

import { useMessage } from '../../model/message-context';
import { PartCard } from './PartCard';

/**
 * What happened to each write, in plain words. Only a verified action (its outcome read back from the record) gets
 * the verified style; pending and failed say so and never imply success.
 */
export function ActionStatuses() {
  const { t } = useTranslation();
  const { message } = useMessage();
  if (message.action_statuses.length === 0) {
    return null;
  }
  return (
    <ul className="flex flex-col gap-3" aria-label={t('parts.actions.title')}>
      {message.action_statuses.map((action, index) => (
        <li key={`${action.action}-${String(index)}`}>
          <PartCard
            title={t(`parts.actionKinds.${action.action}`)}
            meta={<StatusPill status={action.status} />}
          >
            <p className="text-small text-fg">{t(`parts.actions.${action.status}`)}</p>
            {(action.reference !== null || action.evidence !== null) && (
              <dl className="grid grid-cols-1 gap-2 text-small sm:grid-cols-2">
                {action.reference !== null && (
                  <div className="flex flex-col">
                    <dt className="text-fg-muted">{t('parts.actions.reference')}</dt>
                    <dd className="font-mono break-all text-fg">{action.reference}</dd>
                  </div>
                )}
                {action.evidence !== null && (
                  <div className="flex flex-col">
                    <dt className="text-fg-muted">{t('parts.actions.evidence')}</dt>
                    <dd className="font-mono break-all text-fg">{action.evidence}</dd>
                  </div>
                )}
              </dl>
            )}
          </PartCard>
        </li>
      ))}
    </ul>
  );
}
