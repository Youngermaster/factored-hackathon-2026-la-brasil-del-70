import { useTranslation } from 'react-i18next';
import { Link, useSearchParams } from 'react-router';

import { errorMessageKey, errorRequestId } from '@/shared/api';
import { useFormat } from '@/shared/i18n';
import {
  Badge,
  Button,
  DataTable,
  EmptyState,
  ErrorState,
  InboxIcon,
  Skeleton,
  SkeletonGroup,
  useTableSort,
} from '@/shared/ui';

import { useHandoffs, type HandoffView } from '../api/handoffs';
import { readFilters } from '../model/filters';
import { PRIORITY_RANK } from '../model/sla';
import { useNow } from '../model/use-now';
import { useInboxLabels } from './labels';
import { SlaText } from './SlaText';

type SortKey = 'priority' | 'sla_due' | 'created_at';

function compare(a: HandoffView, b: HandoffView, key: SortKey): number {
  if (key === 'priority') {
    return PRIORITY_RANK[a.priority] - PRIORITY_RANK[b.priority];
  }
  return a[key].localeCompare(b[key]);
}

/** The handoff inbox: the server filters (from the URL), the table sorts, and every state is designed. */
export function HandoffList() {
  const { t } = useTranslation();
  const format = useFormat();
  const labels = useInboxLabels();
  const now = useNow();
  const [params] = useSearchParams();
  const filters = readFilters(params);
  const handoffs = useHandoffs(filters);
  const table = useTableSort<HandoffView, SortKey>(
    handoffs.data?.handoffs ?? [],
    { key: 'sla_due', direction: 'ascending' },
    compare,
  );

  if (handoffs.isPending) {
    return (
      <SkeletonGroup label={t('inbox.loading')}>
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-10 w-full" />
      </SkeletonGroup>
    );
  }
  if (handoffs.isError) {
    return (
      <ErrorState
        title={t('inbox.error')}
        description={t(errorMessageKey(handoffs.error))}
        requestId={errorRequestId(handoffs.error)}
        action={
          <Button variant="secondary" onClick={() => void handoffs.refetch()}>
            {t('common.retry')}
          </Button>
        }
      />
    );
  }
  if (handoffs.data.handoffs.length === 0) {
    return (
      <EmptyState
        icon={InboxIcon}
        title={Object.keys(filters).length > 0 ? t('inbox.emptyFiltered') : t('inbox.emptyTitle')}
        description={t('inbox.emptyBody')}
      />
    );
  }
  return (
    <DataTable.Root caption={t('inbox.tableCaption', { count: handoffs.data.handoffs.length })}>
      <DataTable.Head>
        <tr>
          <DataTable.HeaderCell
            sort={table.directionOf('priority')}
            onSort={() => {
              table.sortBy('priority');
            }}
          >
            {t('inbox.columns.priority')}
          </DataTable.HeaderCell>
          <DataTable.HeaderCell>{t('inbox.columns.request')}</DataTable.HeaderCell>
          <DataTable.HeaderCell>{t('inbox.columns.reason')}</DataTable.HeaderCell>
          <DataTable.HeaderCell
            sort={table.directionOf('sla_due')}
            onSort={() => {
              table.sortBy('sla_due');
            }}
          >
            {t('inbox.columns.sla')}
          </DataTable.HeaderCell>
          <DataTable.HeaderCell>{t('inbox.columns.status')}</DataTable.HeaderCell>
          <DataTable.HeaderCell
            sort={table.directionOf('created_at')}
            onSort={() => {
              table.sortBy('created_at');
            }}
          >
            {t('inbox.columns.created')}
          </DataTable.HeaderCell>
        </tr>
      </DataTable.Head>
      <DataTable.Body>
        {table.rows.map((handoff) => (
          <DataTable.Row key={handoff.handoff_id} data-handoff-id={handoff.handoff_id}>
            <DataTable.Cell className="whitespace-nowrap">
              <Badge tone={handoff.priority === 'critical' ? 'risk' : 'neutral'}>
                {labels.value('priority', handoff.priority)}
              </Badge>
            </DataTable.Cell>
            <DataTable.Cell className="min-w-64">
              <Link
                to={`/console/inbox/${handoff.handoff_id}`}
                className="font-semibold text-fg underline-offset-4 hover:underline"
              >
                {labels.code('intent', handoff.request.intent)}
              </Link>
              <span className="line-clamp-2 block text-caption text-fg-secondary">
                {handoff.request.summary}
              </span>
              <span className="block text-caption text-fg-muted">
                {labels.workflow(handoff.workflow?.id)} {' / '}
                {labels.value('language', handoff.language)}
              </span>
            </DataTable.Cell>
            <DataTable.Cell>
              {labels.value('reason', handoff.escalation_reason.code)}
            </DataTable.Cell>
            <DataTable.Cell>
              <SlaText due={handoff.sla_due} now={now} />
            </DataTable.Cell>
            <DataTable.Cell>{labels.value('status', handoff.status)}</DataTable.Cell>
            <DataTable.Cell className="whitespace-nowrap text-fg-secondary">
              <time dateTime={handoff.created_at}>{format.dateTime(handoff.created_at)}</time>
            </DataTable.Cell>
          </DataTable.Row>
        ))}
      </DataTable.Body>
    </DataTable.Root>
  );
}
