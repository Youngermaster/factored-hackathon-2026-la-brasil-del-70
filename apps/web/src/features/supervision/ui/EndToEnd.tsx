import { Fragment, useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router';

import {
  RateCell,
  SystemLabel,
  systemCode,
  useSummaries,
  type EvaluationSummary,
  type OutcomeMetrics,
} from '@/features/eval-report';
import { errorMessageKey, errorRequestId } from '@/shared/api';
import { useFormat } from '@/shared/i18n';
import { Button, DataTable, ErrorState, Skeleton, TextLink } from '@/shared/ui';

import { latestComparableRun, WORKFLOWS } from '../model/evidence';
import { Section } from './Section';

const AGGREGATE = 'aggregate';
type Row = (typeof WORKFLOWS)[number] | typeof AGGREGATE;

function metricsOf(summary: EvaluationSummary, row: Row): OutcomeMetrics | undefined {
  return row === AGGREGATE
    ? summary.aggregate
    : summary.workflows.find((item) => item.workflow === row);
}

/**
 * The newest published run with the proposed system: safe automated resolution per workflow and system (B0, B1, P)
 * with its interval, the cost per resolution next to it, the four workflows before the aggregate. It reads the same
 * cached summaries as the dashboard and the evaluation view.
 */
export function EndToEnd() {
  const { t } = useTranslation();
  const format = useFormat();
  const summaries = useSummaries();
  const run = useMemo(() => latestComparableRun(summaries.data?.summaries ?? []), [summaries.data]);
  const systems = (run?.summaries ?? []).filter((summary) => {
    const code = systemCode(summary.system);
    return code === 'b0' || code === 'b1' || code === 'p';
  });
  const rows: readonly Row[] = [...WORKFLOWS, AGGREGATE];
  const name = (summary: EvaluationSummary) => {
    const code = systemCode(summary.system);
    return code === null ? summary.system : t(`eval.systems.${code}`);
  };
  const usd = (value: string | null) =>
    value === null ? (
      <span className="text-fg-muted">{t('eval.notDefined')}</span>
    ) : (
      format.money({ amount: value, currency: 'USD' })
    );
  let body;
  if (summaries.isPending) {
    body = <Skeleton className="h-64 w-full" />;
  } else if (summaries.isError) {
    body = (
      <ErrorState
        title={t('supervision.evaluation.error')}
        description={t(errorMessageKey(summaries.error))}
        requestId={errorRequestId(summaries.error)}
        action={
          <Button variant="secondary" onClick={() => void summaries.refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  } else if (run === undefined || systems.length === 0) {
    body = <p className="text-small text-fg-muted">{t('supervision.evaluation.empty')}</p>;
  } else {
    const first = systems[0];
    body = (
      <>
        <DataTable.Root caption={t('supervision.evaluation.caption', { run: run.runId })}>
          <DataTable.Head>
            <tr>
              <DataTable.HeaderCell>{t('supervision.evaluation.workflow')}</DataTable.HeaderCell>
              {systems.map((summary) => (
                <Fragment key={summary.system}>
                  <DataTable.HeaderCell numeric>
                    <SystemLabel summary={summary} />
                  </DataTable.HeaderCell>
                  <DataTable.HeaderCell numeric>
                    <span className="sr-only">
                      {t('supervision.evaluation.cost', { system: name(summary) })}
                    </span>
                    <span aria-hidden="true">{t('eval.rows.cost_resolution')}</span>
                  </DataTable.HeaderCell>
                </Fragment>
              ))}
            </tr>
          </DataTable.Head>
          <DataTable.Body>
            {rows.map((row) => (
              <DataTable.Row key={row} className={row === AGGREGATE ? 'border-t-2' : undefined}>
                <th scope="row" className="px-4 py-3 text-left align-top font-medium text-fg">
                  {row === AGGREGATE
                    ? t('supervision.evaluation.aggregate')
                    : t(`glass.workflows.${row}`)}
                </th>
                {systems.map((summary) => {
                  const metrics = metricsOf(summary, row);
                  return (
                    <Fragment key={summary.system}>
                      <DataTable.Cell numeric>
                        {metrics === undefined ? (
                          <span className="text-fg-muted">{t('eval.notDefined')}</span>
                        ) : (
                          <RateCell metric={metrics.safe_automated_resolution} />
                        )}
                      </DataTable.Cell>
                      <DataTable.Cell numeric>
                        {metrics === undefined ? usd(null) : usd(metrics.cost_per_resolution_usd)}
                      </DataTable.Cell>
                    </Fragment>
                  );
                })}
              </DataTable.Row>
            ))}
          </DataTable.Body>
        </DataTable.Root>
        {first !== undefined && (
          <p className="text-caption text-fg-muted">
            {t('supervision.evaluation.meta', {
              dataset: run.datasetVersion,
              generated: format.dateTime(run.generatedAt),
              sha: first.git_sha.slice(0, 7),
            })}{' '}
            {t('supervision.evaluation.costNote')}
          </p>
        )}
      </>
    );
  }
  return (
    <Section
      id="supervision-evaluation"
      title={t('supervision.evaluation.title')}
      intro={t('supervision.evaluation.intro')}
      aside={
        <span className="flex flex-wrap gap-4 text-small">
          <TextLink asChild>
            <Link to="/console/dashboard">{t('supervision.evaluation.openDashboard')}</Link>
          </TextLink>
          <TextLink asChild>
            <Link to="/console/evaluation">{t('supervision.evaluation.openEvaluation')}</Link>
          </TextLink>
        </span>
      }
    >
      {body}
    </Section>
  );
}
