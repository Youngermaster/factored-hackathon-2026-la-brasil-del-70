import type { UseQueryResult } from '@tanstack/react-query';
import { useTranslation } from 'react-i18next';

import { errorMessageKey, errorRequestId, hasProblem } from '@/shared/api';
import { Button, EmptyState, ErrorState, Skeleton, SkeletonGroup, TraceIcon } from '@/shared/ui';

import type { TraceRecord } from '../api/trace';
import type { TraceView } from '../model/scope';
import { TurnTrace } from './TurnTrace';

/** The records of one conversation with every state designed: none yet, loading, not found, failed, and loaded. */
export function TraceBody({
  query,
  view,
  excerpts,
}: {
  readonly query: UseQueryResult<{ readonly records: readonly TraceRecord[] }>;
  readonly view: TraceView;
  readonly excerpts?: ReadonlyMap<string, ReadonlyMap<string, string>>;
}) {
  const { t } = useTranslation();
  if (query.isPending && query.fetchStatus === 'idle') {
    return (
      <EmptyState
        icon={TraceIcon}
        title={t('glass.emptyTitle')}
        description={t('glass.emptyBody')}
      />
    );
  }
  if (query.isPending) {
    return (
      <SkeletonGroup label={t('glass.loading')}>
        <Skeleton className="h-24 w-full" />
        <Skeleton className="h-24 w-full" />
      </SkeletonGroup>
    );
  }
  if (query.isError) {
    if (hasProblem(query.error, 'resource-not-found')) {
      return <EmptyState title={t('glass.notFoundTitle')} description={t('glass.notFoundBody')} />;
    }
    return (
      <ErrorState
        title={t('glass.error')}
        description={t(errorMessageKey(query.error))}
        requestId={errorRequestId(query.error)}
        action={
          <Button
            variant="secondary"
            onClick={() => {
              void query.refetch();
            }}
          >
            {t('common.retry')}
          </Button>
        }
      />
    );
  }
  if (query.data.records.length === 0) {
    return (
      <EmptyState
        icon={TraceIcon}
        title={t('glass.emptyTitle')}
        description={t('glass.emptyBody')}
      />
    );
  }
  return (
    <>
      <h2 className="sr-only">{t('glass.turns')}</h2>
      <ol className="flex flex-col gap-3">
        {query.data.records.map((record, index) => (
          <li key={record.turn_id}>
            <TurnTrace
              record={record}
              index={index}
              latest={index === query.data.records.length - 1}
              view={view}
              excerpts={excerpts?.get(record.turn_id)}
            />
          </li>
        ))}
      </ol>
    </>
  );
}
