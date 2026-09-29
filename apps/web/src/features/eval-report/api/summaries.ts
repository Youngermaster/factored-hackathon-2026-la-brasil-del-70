import { useQuery } from '@tanstack/react-query';

import { queryKeys, unwrap, useApi, type Schema } from '@/shared/api';

export type EvaluationSummary = Schema<'EvaluationSummary'>;
export type OutcomeMetrics = Schema<'OutcomeMetrics'>;
export type SliceSummary = Schema<'SliceSummary'>;

/** The published evaluation summaries, newest first. Empty until the harness publishes a run. */
export function useSummaries() {
  const { client } = useApi();
  return useQuery({
    queryKey: queryKeys.evaluation.summaries(),
    queryFn: () => unwrap(client.GET('/v1/eval/summaries')),
  });
}
