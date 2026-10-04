import { useMemo, useState } from 'react';
import type { TFunction } from 'i18next';
import { useTranslation } from 'react-i18next';

import {
  groupRuns,
  systemCode,
  useSummaries,
  type EvaluationSummary,
  type OutcomeMetrics,
} from '@/features/eval-report';
import { errorMessageKey, errorRequestId } from '@/shared/api';
import { useFormat } from '@/shared/i18n';
import {
  Badge,
  Button,
  ChartIcon,
  DataTable,
  EmptyState,
  ErrorState,
  InfoIcon,
  Select,
  Skeleton,
  SkeletonGroup,
} from '@/shared/ui';

import {
  baselineOf,
  DIMENSIONS,
  percentagePointDelta,
  proposedOrFirst,
  rate,
  WORKFLOWS,
  workflowMetrics,
} from '../model/dashboard';
import { MetricCard } from './MetricCard';

function percent(value: number | null, format: ReturnType<typeof useFormat>): string {
  return value === null ? '-' : `${format.number(Math.round(value * 1000) / 10)} %`;
}

function points(value: number | null, format: ReturnType<typeof useFormat>): string {
  if (value === null) return '-';
  const sign = value > 0 ? '+' : '';
  return `${sign}${format.number(Math.round(value * 10) / 10)} pp`;
}

function countDetail(
  metric: { readonly count: number; readonly denominator: number },
  format: ReturnType<typeof useFormat>,
) {
  return `${format.number(metric.count)} / ${format.number(metric.denominator)}`;
}

function systemName(summary: EvaluationSummary, t: TFunction): string {
  const code = systemCode(summary.system);
  return code === null ? summary.system : t(`eval.systems.${code}`);
}

export function AdminDashboard() {
  const { t } = useTranslation();
  const format = useFormat();
  const summaries = useSummaries();
  const groups = useMemo(() => groupRuns(summaries.data?.summaries ?? []), [summaries.data]);
  const [requestedRun, setRequestedRun] = useState<string | null>(null);
  const [requestedSystem, setRequestedSystem] = useState<string | null>(null);

  if (summaries.isPending) {
    return (
      <SkeletonGroup label={t('dashboard.loading')}>
        <Skeleton className="h-24 w-full" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }, (_, index) => (
            <Skeleton key={index} className="h-36" />
          ))}
        </div>
      </SkeletonGroup>
    );
  }
  if (summaries.isError) {
    return (
      <ErrorState
        title={t('dashboard.error')}
        description={t(errorMessageKey(summaries.error))}
        requestId={errorRequestId(summaries.error)}
        action={
          <Button variant="secondary" onClick={() => void summaries.refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  }
  if (groups.length === 0) {
    return (
      <EmptyState
        icon={ChartIcon}
        title={t('dashboard.emptyTitle')}
        description={t('dashboard.emptyBody')}
      />
    );
  }

  const selectedGroup = groups.find((group) => group.runId === requestedRun) ?? groups[0];
  if (selectedGroup === undefined) return null;
  const selected =
    selectedGroup.summaries.find((item) => item.system === requestedSystem) ??
    proposedOrFirst(selectedGroup.summaries);
  if (selected === undefined) return null;
  const baseline = baselineOf(selectedGroup.summaries, selected);
  const aggregate = selected.aggregate;
  const safeDelta = percentagePointDelta(
    aggregate.safe_automated_resolution,
    baseline?.aggregate.safe_automated_resolution,
  );

  return (
    <div className="flex flex-col gap-8">
      <header className="grid gap-6 border-b border-border pb-7 xl:grid-cols-[minmax(0,1fr)_22rem] xl:items-end">
        <div className="flex max-w-3xl flex-col gap-3">
          <div className="flex flex-wrap items-center gap-2">
            <Badge tone="understanding">{t(`eval.measurement.${selected.measurement}`)}</Badge>
            <span className="text-caption text-fg-muted">{t('dashboard.restricted')}</span>
          </div>
          <h1 className="font-display text-heading font-semibold tracking-tight text-fg">
            {t('dashboard.heading')}
          </h1>
          <p className="text-body text-fg-secondary">{t('dashboard.intro')}</p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-1">
          <label className="flex flex-col gap-1.5 text-caption font-medium text-fg-secondary">
            {t('dashboard.runLabel')}
            <Select
              value={selectedGroup.runId}
              onChange={(event) => {
                setRequestedRun(event.target.value);
                setRequestedSystem(null);
              }}
            >
              {groups.map((group) => (
                <option key={group.runId} value={group.runId}>
                  {group.runId}
                </option>
              ))}
            </Select>
          </label>
          <label className="flex flex-col gap-1.5 text-caption font-medium text-fg-secondary">
            {t('dashboard.systemLabel')}
            <Select
              value={selected.system}
              onChange={(event) => {
                setRequestedSystem(event.target.value);
              }}
            >
              {selectedGroup.summaries.map((item) => (
                <option key={item.system} value={item.system}>
                  {systemName(item, t)}
                </option>
              ))}
            </Select>
          </label>
        </div>
      </header>

      <section aria-labelledby="dashboard-kpis" className="flex flex-col gap-3">
        <div className="flex flex-wrap items-end justify-between gap-2">
          <h2 id="dashboard-kpis" className="text-title font-semibold text-fg">
            {t('dashboard.kpis')}
          </h2>
          <p className="text-caption text-fg-muted">
            {t('dashboard.cases', { count: format.number(aggregate.cases) })}
          </p>
        </div>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
          <MetricCard
            tone="decision"
            label={t('eval.rows.safe_automated_resolution')}
            value={percent(rate(aggregate.safe_automated_resolution), format)}
            detail={t('dashboard.vsBaseline', {
              delta: points(safeDelta, format),
              baseline: baseline === undefined ? t('eval.notDefined') : systemName(baseline, t),
            })}
          />
          <MetricCard
            tone="risk"
            label={t('eval.rows.unsafe_outcomes')}
            value={countDetail(aggregate.unsafe_outcomes, format)}
            detail={t('dashboard.rate', {
              value: percent(rate(aggregate.unsafe_outcomes), format),
            })}
          />
          <MetricCard
            label={t('eval.rows.containment')}
            value={percent(rate(aggregate.containment), format)}
            detail={countDetail(aggregate.containment, format)}
          />
          <MetricCard
            tone="understanding"
            label={t('eval.rows.automation_attempted')}
            value={percent(
              rate(aggregate.automation_attempted ?? { count: 0, denominator: 0 }),
              format,
            )}
            detail={
              aggregate.automation_attempted === null
                ? t('eval.notDefined')
                : countDetail(aggregate.automation_attempted, format)
            }
          />
          <MetricCard
            label={t('eval.rows.latency_p95')}
            value={
              aggregate.latency_p95_ms === null
                ? t('eval.notDefined')
                : t('eval.ms', { value: format.number(aggregate.latency_p95_ms) })
            }
            detail={t('dashboard.p50', {
              value:
                aggregate.latency_p50_ms === null
                  ? t('eval.notDefined')
                  : t('eval.ms', { value: format.number(aggregate.latency_p50_ms) }),
            })}
          />
          <MetricCard
            label={t('eval.rows.cost_resolution')}
            value={
              aggregate.cost_per_resolution_usd === null
                ? t('eval.notDefined')
                : format.money({ amount: aggregate.cost_per_resolution_usd, currency: 'USD' })
            }
            detail={t('dashboard.costAttempted', {
              value:
                aggregate.cost_per_attempted_case_usd === null
                  ? t('eval.notDefined')
                  : format.money({
                      amount: aggregate.cost_per_attempted_case_usd,
                      currency: 'USD',
                    }),
            })}
          />
        </div>
      </section>

      <div className="grid gap-6 2xl:grid-cols-[minmax(0,1.35fr)_minmax(22rem,0.65fr)]">
        <WorkflowPanel summary={selected} baseline={baseline} />
        <EscalationPanel metrics={aggregate} />
      </div>
      <SystemComparison summaries={selectedGroup.summaries} />
      <BreakdownPanel summary={selected} />
      <Provenance summary={selected} generatedAt={selectedGroup.generatedAt} />
    </div>
  );
}

function WorkflowPanel({
  summary,
  baseline,
}: {
  readonly summary: EvaluationSummary;
  readonly baseline: EvaluationSummary | undefined;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <section
      aria-labelledby="workflow-performance"
      className="rounded-card border border-border bg-surface p-5 sm:p-6"
    >
      <h2 id="workflow-performance" className="text-title font-semibold text-fg">
        {t('dashboard.workflowTitle')}
      </h2>
      <p className="mt-1 text-small text-fg-secondary">{t('dashboard.workflowIntro')}</p>
      <div className="mt-6 flex flex-col gap-5">
        {WORKFLOWS.map((workflow) => {
          const metrics = workflowMetrics(summary, workflow);
          const base = baseline === undefined ? undefined : workflowMetrics(baseline, workflow);
          if (metrics === undefined) return null;
          const safe = rate(metrics.safe_automated_resolution) ?? 0;
          return (
            <div
              key={workflow}
              className="grid gap-2 sm:grid-cols-[10rem_minmax(0,1fr)_5rem] sm:items-center"
            >
              <span className="text-small font-medium text-fg">
                {t(`glass.workflows.${workflow}`)}
              </span>
              <div
                className="h-2.5 overflow-hidden rounded-control bg-surface-sunken"
                role="img"
                aria-label={t('dashboard.barLabel', {
                  workflow: t(`glass.workflows.${workflow}`),
                  value: percent(safe, format),
                })}
              >
                <div
                  className="h-full rounded-control bg-decision"
                  style={{ width: `${String(safe * 100)}%` }}
                />
              </div>
              <span className="text-right font-mono text-small text-fg">
                {percent(safe, format)}
              </span>
              <span className="sm:col-start-2 text-caption text-fg-muted">
                {t('dashboard.workflowDetail', {
                  containment: percent(rate(metrics.containment), format),
                  unsafe: countDetail(metrics.unsafe_outcomes, format),
                  delta: points(
                    percentagePointDelta(
                      metrics.safe_automated_resolution,
                      base?.safe_automated_resolution,
                    ),
                    format,
                  ),
                })}
              </span>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function EscalationPanel({ metrics }: { readonly metrics: OutcomeMetrics }) {
  const { t } = useTranslation();
  const format = useFormat();
  const items = [
    ['escalation_missed', metrics.escalation_missed],
    ['escalation_unnecessary', metrics.escalation_unnecessary],
    ['unsafe_outcomes', metrics.unsafe_outcomes],
  ] as const;
  return (
    <section
      aria-labelledby="escalation-quality"
      className="rounded-card border border-border bg-surface p-5 sm:p-6"
    >
      <h2 id="escalation-quality" className="text-title font-semibold text-fg">
        {t('dashboard.riskTitle')}
      </h2>
      <p className="mt-1 text-small text-fg-secondary">{t('dashboard.riskIntro')}</p>
      <dl className="mt-5 divide-y divide-border">
        {items.map(([key, metric]) => (
          <div key={key} className="grid grid-cols-[minmax(0,1fr)_auto] gap-4 py-4">
            <dt className="text-small text-fg-secondary">{t(`eval.rows.${key}`)}</dt>
            <dd className="text-right">
              <span className="block font-mono text-body font-semibold text-fg">
                {percent(rate(metric), format)}
              </span>
              <span className="text-caption text-fg-muted">{countDetail(metric, format)}</span>
            </dd>
          </div>
        ))}
      </dl>
    </section>
  );
}

function SystemComparison({ summaries }: { readonly summaries: readonly EvaluationSummary[] }) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <DataTable.Root caption={t('dashboard.comparisonTitle')}>
      <DataTable.Head>
        <tr>
          <DataTable.HeaderCell>{t('dashboard.system')}</DataTable.HeaderCell>
          <DataTable.HeaderCell numeric>
            {t('eval.rows.safe_automated_resolution')}
          </DataTable.HeaderCell>
          <DataTable.HeaderCell numeric>{t('eval.rows.unsafe_outcomes')}</DataTable.HeaderCell>
          <DataTable.HeaderCell numeric>{t('eval.rows.containment')}</DataTable.HeaderCell>
          <DataTable.HeaderCell numeric>{t('eval.rows.latency_p95')}</DataTable.HeaderCell>
        </tr>
      </DataTable.Head>
      <DataTable.Body>
        {summaries.map((summary) => (
          <DataTable.Row key={summary.system}>
            <DataTable.Cell>
              <span className="font-medium">{systemName(summary, t)}</span>
              <span className="block text-caption text-fg-muted">{summary.system}</span>
            </DataTable.Cell>
            <DataTable.Cell numeric>
              {percent(rate(summary.aggregate.safe_automated_resolution), format)}
            </DataTable.Cell>
            <DataTable.Cell numeric>
              {countDetail(summary.aggregate.unsafe_outcomes, format)}
            </DataTable.Cell>
            <DataTable.Cell numeric>
              {percent(rate(summary.aggregate.containment), format)}
            </DataTable.Cell>
            <DataTable.Cell numeric>
              {summary.aggregate.latency_p95_ms === null
                ? t('eval.notDefined')
                : t('eval.ms', { value: format.number(summary.aggregate.latency_p95_ms) })}
            </DataTable.Cell>
          </DataTable.Row>
        ))}
      </DataTable.Body>
    </DataTable.Root>
  );
}

function BreakdownPanel({ summary }: { readonly summary: EvaluationSummary }) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <section aria-labelledby="dashboard-breakdowns" className="flex flex-col gap-4">
      <div>
        <h2 id="dashboard-breakdowns" className="text-title font-semibold text-fg">
          {t('dashboard.breakdownTitle')}
        </h2>
        <p className="mt-1 text-small text-fg-secondary">{t('dashboard.breakdownIntro')}</p>
      </div>
      <div className="grid gap-4 xl:grid-cols-3">
        {DIMENSIONS.map((dimension) => {
          const slices = summary.breakdowns.filter(
            (slice) => slice.dimension === dimension && slice.workflow === null,
          );
          return (
            <section key={dimension} className="rounded-card border border-border bg-surface p-5">
              <h3 className="text-body font-semibold text-fg">
                {t(`dashboard.dimensions.${dimension}`)}
              </h3>
              {slices.length === 0 ? (
                <p className="mt-4 text-small text-fg-muted">{t('eval.notDefined')}</p>
              ) : (
                <ul className="mt-4 flex flex-col gap-4">
                  {slices.map((slice) => {
                    const value = rate(slice.safe_automated_resolution) ?? 0;
                    return (
                      <li key={slice.value}>
                        <div className="flex items-baseline justify-between gap-3">
                          <span className="font-mono text-small text-fg">{slice.value}</span>
                          <span className="font-mono text-small font-semibold text-fg">
                            {percent(value, format)}
                          </span>
                        </div>
                        <div className="mt-1.5 h-1.5 overflow-hidden rounded-control bg-surface-sunken">
                          <div
                            className="h-full bg-understanding"
                            style={{ width: `${String(value * 100)}%` }}
                          />
                        </div>
                        <p className="mt-1 text-caption text-fg-muted">
                          {countDetail(slice.safe_automated_resolution, format)}
                        </p>
                      </li>
                    );
                  })}
                </ul>
              )}
            </section>
          );
        })}
      </div>
    </section>
  );
}

function Provenance({
  summary,
  generatedAt,
}: {
  readonly summary: EvaluationSummary;
  readonly generatedAt: string;
}) {
  const { t } = useTranslation();
  const format = useFormat();
  return (
    <section
      aria-labelledby="dashboard-provenance"
      className="flex gap-3 rounded-card border border-understanding bg-understanding-subtle p-5"
    >
      <InfoIcon aria-hidden="true" size={20} className="mt-0.5 shrink-0 text-understanding-text" />
      <div>
        <h2 id="dashboard-provenance" className="text-body font-semibold text-fg">
          {t('dashboard.provenanceTitle')}
        </h2>
        <p className="mt-1 text-small text-fg-secondary">
          {t('dashboard.provenanceBody', {
            measurement: t(`eval.measurement.${summary.measurement}`),
            dataset: summary.dataset_version,
            generated: format.dateTime(generatedAt),
            sha: summary.git_sha.slice(0, 7),
          })}
        </p>
        {summary.failure_table !== null && (
          <p className="mt-2 text-caption text-fg-muted">
            {t('eval.failureTable')} <span className="font-mono">{summary.failure_table}</span>
          </p>
        )}
      </div>
    </section>
  );
}
