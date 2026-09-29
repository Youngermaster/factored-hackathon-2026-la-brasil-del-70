import { useId } from 'react';
import { useTranslation } from 'react-i18next';

import { ShieldIcon } from '@/shared/ui';

import { isStaffRecord } from '../../model/records';
import { useRecord } from '../../model/scope';

/**
 * The evaluator-only part of a record, set apart from what the customer sees: the session risk tier, the trust
 * events and safety interventions this turn added, and the trace id. The estimate values are in the credit panel.
 */
export function Internal() {
  const { t } = useTranslation();
  const id = useId();
  const { record } = useRecord();
  if (!isStaffRecord(record)) {
    return null;
  }
  return (
    <section
      aria-labelledby={id}
      className="flex flex-col gap-2 rounded-card border border-dashed border-border-strong bg-surface-sunken p-3 text-caption"
    >
      <h3 id={id} className="flex items-center gap-1.5 text-small font-semibold text-fg">
        <ShieldIcon aria-hidden="true" size={16} />
        {t('glass.internal.title')}
      </h3>
      <p className="text-fg-secondary">{t('glass.internal.body')}</p>
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-fg">
        <dt>{t('glass.internal.riskTier')}</dt>
        <dd>{t(`glass.internal.tiers.${record.risk_tier}`)}</dd>
        <dt>{t('glass.internal.trustEvents')}</dt>
        <dd className="font-mono break-all">
          {record.trust_events_added.length === 0
            ? t('glass.none')
            : record.trust_events_added.join(', ')}
        </dd>
        <dt>{t('glass.internal.interventions')}</dt>
        <dd className="font-mono break-all">
          {record.safety_interventions.length === 0
            ? t('glass.none')
            : record.safety_interventions.join(', ')}
        </dd>
        <dt>{t('glass.internal.authLevel')}</dt>
        <dd>{t(`session.authLevels.${record.auth_level}`)}</dd>
        <dt>{t('glass.internal.traceId')}</dt>
        <dd className="font-mono break-all">{record.trace_id ?? t('glass.none')}</dd>
      </dl>
    </section>
  );
}
