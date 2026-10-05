import { useQuery } from '@tanstack/react-query';

import { queryKeys, toApiError, unwrap, useApi, type Schema } from '@/shared/api';

export type ModelInventoryResponse = Schema<'ModelInventoryResponse'>;
export type ModelInventory = Schema<'ModelInventory'>;
export type ServedModel = Schema<'ServedModel'>;
export type ModelCard = Schema<'ModelCard'>;
export type CardMetric = Schema<'CardMetric'>;
export type PromotionDecision = Schema<'PromotionDecision'>;
export type PromotionRow = Schema<'PromotionRow'>;
export type LlmConfiguration = Schema<'LlmConfiguration'>;
export type HealthDetails = Schema<'HealthDetailsResponse'>;

/** Configuration and published evidence only: it changes when the process restarts, so it stays fresh for minutes. */
const INVENTORY_STALE_MS = 5 * 60_000;
/** The degradation level moves with the dependencies; the view polls it while open. */
export const HEALTH_REFRESH_MS = 30_000;

/** What the process serves and the offline model cards (`GET /v1/eval/models`, evaluator only). */
export function useModelInventory() {
  const { client } = useApi();
  return useQuery({
    queryKey: queryKeys.supervision.models(),
    queryFn: () => unwrap(client.GET('/v1/eval/models')),
    staleTime: INVENTORY_STALE_MS,
  });
}

function isHealthDetails(value: unknown): value is HealthDetails {
  return typeof value === 'object' && value !== null && 'level' in value && 'components' in value;
}

/**
 * The degradation details. At level L4 the endpoint answers 503 with the same body, which is an answer to show,
 * not an error: only a body without the details shape is thrown.
 */
export async function readHealthDetails(
  request: Promise<{ data?: HealthDetails; error?: unknown; response: Response }>,
): Promise<HealthDetails> {
  const { data, error, response } = await request;
  if (data !== undefined) {
    return data;
  }
  if (response.status === 503 && isHealthDetails(error)) {
    return error;
  }
  throw toApiError(error, response);
}

export function useHealthDetails() {
  const { client } = useApi();
  return useQuery({
    queryKey: queryKeys.health.details(),
    queryFn: () => readHealthDetails(client.GET('/health/details')),
    refetchInterval: HEALTH_REFRESH_MS,
  });
}
