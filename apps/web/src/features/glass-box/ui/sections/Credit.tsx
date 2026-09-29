import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { InfoIcon } from '@/shared/ui';

import { findRule, isStaffRecord, ruleStatus } from '../../model/records';
import { useRecord } from '../../model/scope';
import { Section } from './Section';

/**
 * A credit turn's two components, in two panels that are never merged: the risk estimate (a model's prediction on
 * synthetic data) and the eligibility decision (the synthetic eligibility service's rules). The customer view shows
 * only that an estimate was used and its model; the staff view shows its values.
 */
export function Credit() {
  const { t } = useTranslation();
  const { record } = useRecord();
  const used = isStaffRecord(record)
    ? record.risk_estimates.length
    : record.risk_estimates_used.length;
  if (used === 0 && record.eligibility_assessments.length === 0) {
    return null;
  }
  return (
    <Section tone="neutral" title={t('glass.credit.title')} kind={t('glass.kinds.separated')}>
      <div className="mt-1 flex flex-col gap-3">
        <div className="grid grid-cols-1 gap-3 xl:grid-cols-2">
          <RiskEstimatePanel />
          <EligibilityPanel />
        </div>
        <p className="flex items-start gap-1.5 text-caption text-fg-muted">
          <InfoIcon aria-hidden="true" size={14} className="mt-0.5 shrink-0" />
          {t('glass.credit.separation')}
        </p>
      </div>
    </Section>
  );
}

function RiskEstimatePanel() {
  const { t } = useTranslation();
  const format = useFormat();
  const { record } = useRecord();
  const percent = (value: string) => `${format.number(Math.round(Number(value) * 1000) / 10)} %`;
  return (
    <section
      aria-label={t('glass.credit.riskTitle')}
      className="flex flex-col gap-2 rounded-card border border-understanding bg-understanding-subtle p-3 text-caption"
    >
      <h3 className="text-small font-semibold text-fg">{t('glass.credit.riskTitle')}</h3>
      <p className="text-understanding-text">{t('glass.credit.riskLabel')}</p>
      {isStaffRecord(record)
        ? record.risk_estimates.map((estimate) => (
            <dl
              key={estimate.estimate_id}
              className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-fg"
            >
              <dt>{t('glass.credit.model')}</dt>
              <dd className="font-mono break-all">{estimate.model}</dd>
              <dt>{t('glass.credit.band')}</dt>
              <dd>{t(`glass.credit.bands.${estimate.band}`)}</dd>
              <dt>{t('glass.credit.probability')}</dt>
              <dd className="font-mono">{percent(estimate.probability)}</dd>
              <dt>{t('glass.credit.interval')}</dt>
              <dd className="font-mono">
                {percent(estimate.interval_low)} {t('glass.credit.to')}{' '}
                {percent(estimate.interval_high)}
              </dd>
              <dt>{t('glass.credit.flags')}</dt>
              <dd>
                {estimate.flags.length === 0
                  ? t('glass.credit.noFlags')
                  : estimate.flags.map((flag) => t(`glass.credit.flag.${flag}`)).join(', ')}
              </dd>
              <dt>{t('glass.credit.label')}</dt>
              <dd className="font-mono break-all">{estimate.label_definition}</dd>
            </dl>
          ))
        : record.risk_estimates_used.map((estimate) => (
            <dl
              key={estimate.estimate_id}
              className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-fg"
            >
              <dt>{t('glass.credit.used')}</dt>
              <dd className="font-mono break-all">{estimate.model}</dd>
              <dt>{t('glass.credit.label')}</dt>
              <dd className="font-mono break-all">{estimate.label_definition}</dd>
            </dl>
          ))}
      {!isStaffRecord(record) && <p className="text-fg-muted">{t('glass.credit.valuesHidden')}</p>}
    </section>
  );
}

function EligibilityPanel() {
  const { t } = useTranslation();
  const { record } = useRecord();
  return (
    <section
      aria-label={t('glass.credit.eligibilityTitle')}
      className="flex flex-col gap-2 rounded-card border border-border-strong bg-decision-subtle p-3 text-caption"
    >
      <h3 className="text-small font-semibold text-fg">{t('glass.credit.eligibilityTitle')}</h3>
      {record.eligibility_assessments.length === 0 && <p>{t('glass.credit.noAssessment')}</p>}
      {record.eligibility_assessments.map((assessment) => (
        <div key={assessment.assessment_id} className="flex flex-col gap-1.5 text-fg">
          <p>
            <span className="font-mono break-all">{assessment.service}</span>
          </p>
          <p className="font-semibold">{t(`parts.eligibilityOutcomes.${assessment.outcome}`)}</p>
          <ul className="flex flex-col gap-0.5">
            {assessment.rules.map((rule) => {
              const result = findRule(record, rule.rule_id);
              return (
                <li key={rule.rule_id} className="flex flex-wrap gap-x-2">
                  <span className="font-mono">
                    {rule.rule_id}@{rule.rule_version}
                  </span>
                  <span>
                    {result === undefined
                      ? t('glass.credit.notRecorded')
                      : t(`glass.ruleStatus.${ruleStatus(result)}`)}
                  </span>
                  {result !== undefined && result.clause_refs.length > 0 && (
                    <span className="font-mono text-fg-muted">{result.clause_refs.join(', ')}</span>
                  )}
                </li>
              );
            })}
          </ul>
          {assessment.review_reasons.length > 0 && (
            <p>
              {t('glass.credit.reviewReasons')}{' '}
              {assessment.review_reasons
                .map((reason) => t(`glass.credit.review.${reason}`))
                .join(', ')}
            </p>
          )}
        </div>
      ))}
    </section>
  );
}
