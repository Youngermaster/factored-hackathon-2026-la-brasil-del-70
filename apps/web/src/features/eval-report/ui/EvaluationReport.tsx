import { useTranslation } from 'react-i18next';

import type { Schema } from '@/shared/api';
import { errorMessageKey, errorRequestId } from '@/shared/api';
import { useFormat } from '@/shared/i18n';
import {
  Button,
  ChartIcon,
  EmptyState,
  ErrorState,
  InfoIcon,
  Skeleton,
  SkeletonGroup,
} from '@/shared/ui';

import { useSummaries } from '../api/summaries';
import { groupRuns, type RunGroup } from '../model/systems';
import { Breakdowns } from './Breakdowns';
import { MetricTable } from './MetricTable';

const WORKFLOWS: readonly Schema<'WorkflowId'>[] = [
  'account_inquiry',
  'card_support',
  'dispute',
  'credit',
];
// Identifiers the empty state quotes: a command and a setting name, not copy.
const PUBLISH_COMMAND = 'make eval';
const SUMMARIES_SETTING = 'EVAL_SUMMARIES_DIR';

/**
 * The published evaluation summaries: per run, one table per workflow and then the aggregate (never the aggregate
 * alone), systems side by side, then the breakdowns. Every table names its measurement label.
 */
export function EvaluationReport() {
  const { t } = useTranslation();
  const summaries = useSummaries();
  if (summaries.isPending) {
    return (
      <SkeletonGroup label={t('eval.loading')}>
        <Skeleton className="h-10 w-80" />
        <Skeleton className="h-64 w-full" />
      </SkeletonGroup>
    );
  }
  if (summaries.isError) {
    return (
      <ErrorState
        title={t('eval.error')}
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
  if (summaries.data.summaries.length === 0) {
    return (
      <EmptyState
        icon={ChartIcon}
        title={t('eval.emptyTitle')}
        description={
          <>
            {t('eval.emptyBody')} <code className="font-mono text-fg">{PUBLISH_COMMAND}</code>{' '}
            {t('eval.emptyWhere')} <code className="font-mono text-fg">{SUMMARIES_SETTING}</code>
            {t('eval.emptyAfter')}
          </>
        }
      />
    );
  }
  return (
    <div className="flex flex-col gap-12">
      {groupRuns(summaries.data.summaries).map((group) => (
        <Run key={`${group.runId}-${group.datasetVersion}`} group={group} />
      ))}
    </div>
  );
}

function Run({ group }: { readonly group: RunGroup }) {
  const { t } = useTranslation();
  const format = useFormat();
  const titleId = `run-${group.runId}`;
  const notes = group.summaries.flatMap((summary) => summary.notes);
  const failureTables = [
    ...new Set(
      group.summaries.flatMap((summary) =>
        summary.failure_table === null ? [] : [summary.failure_table],
      ),
    ),
  ];
  return (
    <section aria-labelledby={titleId} className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <h2 id={titleId} className="text-title font-semibold text-fg">
          {t('eval.run', { run: group.runId })}
        </h2>
        <p className="text-small text-fg-secondary">
          {t('eval.runMeta', {
            dataset: group.datasetVersion,
            generated: format.dateTime(group.generatedAt),
            shas: [...new Set(group.summaries.map((summary) => summary.git_sha.slice(0, 7)))].join(
              ', ',
            ),
          })}
        </p>
        {failureTables.map((path) => (
          <p key={path} className="text-small text-fg">
            {t('eval.failureTable')} <span className="font-mono">{path}</span>
          </p>
        ))}
        {notes.length > 0 && (
          <ul className="flex flex-col gap-1 text-small text-fg-secondary">
            {notes.map((note) => (
              <li key={note} className="flex items-start gap-1.5">
                <InfoIcon aria-hidden="true" size={16} className="mt-0.5 shrink-0" />
                {note}
              </li>
            ))}
          </ul>
        )}
      </div>
      {WORKFLOWS.map((workflow) => (
        <MetricTable
          key={workflow}
          caption={t('eval.workflowCaption', { workflow: t(`glass.workflows.${workflow}`) })}
          summaries={group.summaries}
          metricsOf={(summary) => summary.workflows.find((item) => item.workflow === workflow)}
        />
      ))}
      <MetricTable
        caption={t('eval.aggregateCaption')}
        summaries={group.summaries}
        metricsOf={(summary) => summary.aggregate}
      />
      <Breakdowns summaries={group.summaries} />
    </section>
  );
}
