import { useTranslation } from 'react-i18next';

import type { Schema } from '@/shared/api';
import { cx } from '@/shared/lib/cx';
import { CaretRightIcon } from '@/shared/ui';

import { countRules, isPreCheck, ruleStatus } from '../../model/records';
import { useRecord } from '../../model/scope';
import { Section } from './Section';

type Decision = Schema<'Decision'>;

/** The policy kernel's decisions in this turn: per state, the outcome, the decisive rules, and every rule result. */
export function Decisions() {
  const { t } = useTranslation();
  const { record } = useRecord();
  if (record.decisions.length === 0) {
    return null;
  }
  const escalates = record.decisions.some(
    (decision) => decision.kind === 'escalate' || decision.kind === 'refuse',
  );
  return (
    <Section
      tone={escalates ? 'risk' : 'decision'}
      title={t('glass.rules')}
      kind={t('glass.kinds.rules')}
      meta={record.policy_pack_version}
    >
      <ol className="flex flex-col gap-3">
        {record.decisions.map((decision, index) => (
          <li key={`${decision.state}-${String(index)}`}>
            <DecisionItem decision={decision} />
          </li>
        ))}
      </ol>
    </Section>
  );
}

function DecisionItem({ decision }: { readonly decision: Decision }) {
  const { t } = useTranslation();
  const counts = countRules(decision);
  const preCheck = isPreCheck(decision);
  return (
    <details className="group">
      <summary className="flex cursor-pointer list-none items-start gap-1.5 rounded-control">
        <CaretRightIcon
          aria-hidden="true"
          size={14}
          className="mt-1 shrink-0 group-open:rotate-90"
        />
        <span className="flex flex-col">
          <span className="text-fg">
            <span className="font-mono">{decision.state}</span>:{' '}
            {preCheck ? t('glass.preCheck') : t(`glass.decisionKinds.${decision.kind}`)}
          </span>
          <span className="text-caption">
            {t('glass.ruleCounts', { ...counts })}
            {!preCheck && decision.decisive_rule_ids.length > 0 && (
              <>
                {' '}
                {t('glass.decisive')}{' '}
                <span className="font-mono">{decision.decisive_rule_ids.join(', ')}</span>
              </>
            )}
          </span>
          {preCheck && <span className="text-caption">{t('glass.preCheckNote')}</span>}
        </span>
      </summary>
      <table className="mt-2 w-full text-left text-caption">
        <caption className="sr-only">{t('glass.rulesCaption', { state: decision.state })}</caption>
        <thead>
          <tr className="text-fg-muted">
            <th scope="col" className="py-1 pr-2 font-medium">
              {t('glass.rule')}
            </th>
            <th scope="col" className="py-1 pr-2 font-medium">
              {t('glass.result')}
            </th>
            <th scope="col" className="py-1 font-medium">
              {t('glass.reason')}
            </th>
          </tr>
        </thead>
        <tbody>
          {decision.rule_results.map((rule) => {
            const status = ruleStatus(rule);
            return (
              <tr key={rule.rule_id} className="border-t border-border align-top">
                <td className="py-1 pr-2 font-mono break-all text-fg">
                  {rule.rule_id}@{rule.rule_version}
                </td>
                <td
                  className={cx(
                    'py-1 pr-2 whitespace-nowrap',
                    status === 'failed' ? 'font-semibold text-risk-text' : 'text-fg',
                  )}
                >
                  {t(`glass.ruleStatus.${status}`)}
                </td>
                <td className="py-1 font-mono break-all">{rule.reason_code}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </details>
  );
}
