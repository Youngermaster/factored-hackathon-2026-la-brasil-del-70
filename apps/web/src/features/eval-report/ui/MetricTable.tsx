import type { ReactNode } from 'react';
import { useTranslation } from 'react-i18next';

import { useFormat } from '@/shared/i18n';
import { Badge, DataTable } from '@/shared/ui';

import type { EvaluationSummary, OutcomeMetrics } from '../api/summaries';
import { proportion, SMALL_CELL } from '../model/stats';
import { SystemLabel } from './SystemLabel';

type Rate =
  | 'safe_automated_resolution'
  | 'automation_attempted'
  | 'containment'
  | 'escalation_missed'
  | 'escalation_unnecessary'
  | 'unsafe_outcomes';

const RATES: readonly Rate[] = [
  'safe_automated_resolution',
  'automation_attempted',
  'containment',
  'escalation_missed',
  'escalation_unnecessary',
];

/**
 * One slice of the workload (a workflow or the aggregate), the systems side by side: the brief's five outcomes
 * with their sample sizes and 95% intervals, "not defined" where a figure was not published, and small cells flagged.
 */
export function MetricTable({
  caption,
  summaries,
  metricsOf,
}: {
  readonly caption: ReactNode;
  readonly summaries: readonly EvaluationSummary[];
  readonly metricsOf: (summary: EvaluationSummary) => OutcomeMetrics | undefined;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const columns = summaries.map((summary) => ({ summary, metrics: metricsOf(summary) }));
  const row = (label: ReactNode, cell: (metrics: OutcomeMetrics) => ReactNode) => (
    <DataTable.Row>
      <th scope="row" className="px-4 py-3 text-left align-top font-medium text-fg">
        {label}
      </th>
      {columns.map(({ summary, metrics }) => (
        <DataTable.Cell key={summary.system} numeric>
          {metrics === undefined ? <NotDefined /> : cell(metrics)}
        </DataTable.Cell>
      ))}
    </DataTable.Row>
  );
  const ms = (value: number | null) =>
    value === null ? <NotDefined /> : t('eval.ms', { value: format.number(value) });
  const usd = (value: string | null) =>
    value === null ? <NotDefined /> : format.money({ amount: value, currency: 'USD' });
  return (
    <DataTable.Root caption={caption}>
      <DataTable.Head>
        <tr>
          <DataTable.HeaderCell>{t('eval.metric')}</DataTable.HeaderCell>
          {columns.map(({ summary }) => (
            <DataTable.HeaderCell key={summary.system} numeric>
              <SystemLabel summary={summary} />
            </DataTable.HeaderCell>
          ))}
        </tr>
      </DataTable.Head>
      <DataTable.Body>
        {row(t('eval.rows.cases'), (metrics) => (
          <span className="flex flex-col items-end gap-1">
            {format.number(metrics.cases)}
            {metrics.cases < SMALL_CELL && <Badge>{t('eval.small')}</Badge>}
          </span>
        ))}
        {RATES.map((rate) => (
          <RateRow key={rate} rate={rate} row={row} />
        ))}
        {row(t('eval.rows.handoff_completeness'), () => (
          <NotDefined />
        ))}
        {row(t('eval.rows.unsafe_outcomes'), (metrics) => (
          <RateCell metric={metrics.unsafe_outcomes} counts />
        ))}
        {row(t('eval.rows.latency_p50'), (metrics) => ms(metrics.latency_p50_ms))}
        {row(t('eval.rows.latency_p95'), (metrics) => ms(metrics.latency_p95_ms))}
        {row(t('eval.rows.cost_attempted'), (metrics) => usd(metrics.cost_per_attempted_case_usd))}
        {row(t('eval.rows.cost_resolution'), (metrics) => usd(metrics.cost_per_resolution_usd))}
      </DataTable.Body>
    </DataTable.Root>
  );
}

function RateRow({
  rate,
  row,
}: {
  readonly rate: Rate;
  readonly row: (label: ReactNode, cell: (metrics: OutcomeMetrics) => ReactNode) => ReactNode;
}) {
  const { t } = useTranslation();
  return row(t(`eval.rows.${rate}`), (metrics) => {
    const metric = metrics[rate];
    return metric === null ? <NotDefined /> : <RateCell metric={metric} />;
  });
}

export function NotDefined() {
  const { t } = useTranslation();
  return <span className="text-fg-muted">{t('eval.notDefined')}</span>;
}

/** A rate with its sample size and interval; a zero count shows its one-sided upper bound instead. */
export function RateCell({
  metric,
  counts = false,
}: {
  readonly metric: { readonly count: number; readonly denominator: number };
  /** Unsafe outcomes lead with the count over its denominator, as the brief asks. */
  readonly counts?: boolean;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  const value = proportion(metric);
  if (value === null) {
    return <NotDefined />;
  }
  const percent = (rate: number) => `${format.number(Math.round(rate * 1000) / 10)} %`;
  const ofTotal = t('eval.countOf', {
    count: format.number(value.count),
    total: format.number(value.denominator),
  });
  return (
    <span className="flex flex-col items-end gap-0.5">
      <span className="font-semibold text-fg">{counts ? ofTotal : percent(value.rate)}</span>
      <span className="text-caption text-fg-muted">
        {counts ? percent(value.rate) : ofTotal}
        {', '}
        {value.zeroEvents
          ? t('eval.upperBound', { high: percent(value.high) })
          : t('eval.interval', { low: percent(value.low), high: percent(value.high) })}
      </span>
      {value.small && <Badge>{t('eval.small')}</Badge>}
    </span>
  );
}
