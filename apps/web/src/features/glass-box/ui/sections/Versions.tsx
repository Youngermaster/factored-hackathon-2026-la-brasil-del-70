import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';

import { latencyStages } from '../../model/records';
import { useRecord } from '../../model/scope';
import { Section } from './Section';

/** Model, prompt, and policy versions, then the latency breakdown, tokens, and cost of the turn. */
export function Versions() {
  const { t } = useTranslation();
  const format = useFormat();
  const { record } = useRecord();
  const ms = (value: number) => t('glass.ms', { value: format.number(value) });
  return (
    <Section
      tone="neutral"
      title={t('glass.versions')}
      kind={t('glass.kinds.record')}
      meta={ms(record.latency.total_ms)}
    >
      <dl className="grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-0.5 text-caption">
        <dt>{t('glass.models')}</dt>
        <dd className="font-mono break-all text-fg">
          {record.models.length === 0 ? t('glass.none') : record.models.join(', ')}
        </dd>
        <dt>{t('glass.prompts')}</dt>
        <dd className="font-mono break-all text-fg">
          {record.prompts.length === 0 ? t('glass.none') : record.prompts.join(', ')}
        </dd>
        <dt>{t('glass.policyPack')}</dt>
        <dd className="font-mono break-all text-fg">{record.policy_pack_version}</dd>
        <dt>{t('glass.latency')}</dt>
        <dd className="font-mono text-fg">
          {latencyStages(record)
            .map(([stage, value]) => `${stage} ${ms(value)}`)
            .join(', ') || ms(record.latency.total_ms)}
        </dd>
        <dt>{t('glass.tokens')}</dt>
        <dd className="font-mono text-fg">
          {t('glass.tokenCounts', {
            input: format.number(record.token_usage.input_tokens),
            output: format.number(record.token_usage.output_tokens),
          })}
        </dd>
        <dt>{t('glass.cost')}</dt>
        <dd className="font-mono text-fg">
          {format.money({ amount: record.cost_usd, currency: 'USD' })}
        </dd>
      </dl>
    </Section>
  );
}
