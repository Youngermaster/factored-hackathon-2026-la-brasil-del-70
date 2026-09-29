import { useTranslation } from 'react-i18next';

import { DataTable } from '@/shared/ui';

import type { EvaluationSummary, SliceSummary } from '../api/summaries';
import { NotDefined, RateCell } from './MetricTable';
import { SystemLabel } from './SystemLabel';

const DIMENSIONS = ['language', 'dialect', 'segment'] as const;

function sliceKey(slice: SliceSummary): string {
  return `${slice.workflow ?? ''}|${slice.value}`;
}

/**
 * Language, dialect, and segment breakdowns: safe automated resolution per slice and system, with its sample
 * size, interval, and small-cell flag. A dimension no system published is left out.
 */
export function Breakdowns({ summaries }: { readonly summaries: readonly EvaluationSummary[] }) {
  const { t } = useTranslation();
  return DIMENSIONS.map((dimension) => {
    const keys = new Map<string, SliceSummary>();
    for (const summary of summaries) {
      for (const slice of summary.breakdowns) {
        if (slice.dimension === dimension && !keys.has(sliceKey(slice))) {
          keys.set(sliceKey(slice), slice);
        }
      }
    }
    if (keys.size === 0) {
      return null;
    }
    return (
      <DataTable.Root key={dimension} caption={t(`eval.breakdown.${dimension}`)}>
        <DataTable.Head>
          <tr>
            <DataTable.HeaderCell>{t('eval.slice')}</DataTable.HeaderCell>
            {summaries.map((summary) => (
              <DataTable.HeaderCell key={summary.system} numeric>
                <SystemLabel summary={summary} />
              </DataTable.HeaderCell>
            ))}
          </tr>
        </DataTable.Head>
        <DataTable.Body>
          {[...keys.entries()].map(([key, slice]) => (
            <DataTable.Row key={key}>
              <th scope="row" className="px-4 py-3 text-left align-top font-medium text-fg">
                <span className="font-mono">{slice.value}</span>
                <span className="block text-caption font-normal text-fg-muted">
                  {slice.workflow === null
                    ? t('eval.allWorkflows')
                    : t(`glass.workflows.${slice.workflow}`)}
                </span>
              </th>
              {summaries.map((summary) => {
                const match = summary.breakdowns.find(
                  (item) => item.dimension === dimension && sliceKey(item) === key,
                );
                return (
                  <DataTable.Cell key={summary.system} numeric>
                    {match === undefined ? (
                      <NotDefined />
                    ) : (
                      <RateCell metric={match.safe_automated_resolution} />
                    )}
                  </DataTable.Cell>
                );
              })}
            </DataTable.Row>
          ))}
        </DataTable.Body>
      </DataTable.Root>
    );
  });
}
