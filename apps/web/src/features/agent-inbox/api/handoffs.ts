import { skipToken, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { queryKeys, unwrap, useApi, type Schema } from '@/shared/api';

import { toQuery, type HandoffFilters } from '../model/filters';

export type HandoffView = Schema<'HandoffView'>;
export type CreditApplicationView = Schema<'CreditApplicationView'>;

/** The inbox, filtered on the server. The key carries the filters, so each filter set is cached on its own. */
export function useHandoffs(filters: HandoffFilters) {
  const { client } = useApi();
  return useQuery({
    queryKey: queryKeys.handoffs.list({ ...filters }),
    // The due window is turned into an instant when the request is made, so a refetch uses the current time.
    queryFn: () =>
      unwrap(client.GET('/v1/agent/handoffs', { params: { query: toQuery(filters, new Date()) } })),
  });
}

export function useHandoff(handoffId: string | null) {
  const { client } = useApi();
  return useQuery({
    queryKey: queryKeys.handoffs.detail(handoffId ?? ''),
    queryFn:
      handoffId === null
        ? skipToken
        : () =>
            unwrap(
              client.GET('/v1/agent/handoffs/{handoff_id}', {
                params: { path: { handoff_id: handoffId } },
              }),
            ),
  });
}

/** After a claim or a resolution: the detail takes the server's answer, and every list refetches. */
function useSettle() {
  const queryClient = useQueryClient();
  return (handoff: HandoffView) => {
    queryClient.setQueryData(queryKeys.handoffs.detail(handoff.handoff_id), handoff);
    void queryClient.invalidateQueries({ queryKey: [...queryKeys.handoffs.all, 'list'] });
    void queryClient.invalidateQueries({
      queryKey: queryKeys.humanService.detail('agent', handoff.handoff_id),
    });
  };
}

export function useClaimHandoff() {
  const { client } = useApi();
  const settle = useSettle();
  return useMutation({
    mutationFn: (handoffId: string) =>
      unwrap(
        client.POST('/v1/agent/handoffs/{handoff_id}/claim', {
          params: { path: { handoff_id: handoffId } },
        }),
      ),
    onSuccess: settle,
  });
}

export interface ResolveInput {
  readonly handoffId: string;
  readonly outcome: Schema<'HandoffOutcomeCode'>;
  readonly note: string;
}

export function useResolveHandoff() {
  const { client } = useApi();
  const settle = useSettle();
  return useMutation({
    mutationFn: ({ handoffId, outcome, note }: ResolveInput) =>
      unwrap(
        client.POST('/v1/agent/handoffs/{handoff_id}/resolve', {
          params: { path: { handoff_id: handoffId } },
          body: { outcome, note },
        }),
      ),
    onSuccess: settle,
  });
}

/** Credit intakes recorded for human review: read only, never a lending decision. */
export function useCreditApplications() {
  const { client } = useApi();
  return useQuery({
    queryKey: [...queryKeys.creditApplications.all, 'list'],
    queryFn: () => unwrap(client.GET('/v1/agent/credit-applications')),
  });
}

export function useCreditApplication(applicationId: string | null) {
  const { client } = useApi();
  return useQuery({
    queryKey: queryKeys.creditApplications.detail(applicationId ?? ''),
    queryFn:
      applicationId === null
        ? skipToken
        : () =>
            unwrap(
              client.GET('/v1/agent/credit-applications/{application_id}', {
                params: { path: { application_id: applicationId } },
              }),
            ),
  });
}

export type CreditReviewMove = 'review' | 'close';

export interface CreditReviewInput {
  readonly applicationId: string;
  readonly move: CreditReviewMove;
  readonly expectedVersion: number;
}

/**
 * Take an intake into human review, or close one under review. The detail keeps the server's answer (a closed intake
 * without a handoff leaves the review list, so it is not read again), and the list refetches.
 */
export function useMoveCreditApplication() {
  const { client } = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ applicationId, move, expectedVersion }: CreditReviewInput) => {
      const options = {
        params: { path: { application_id: applicationId } },
        body: { expected_version: expectedVersion },
      };
      return unwrap(
        move === 'review'
          ? client.POST('/v1/agent/credit-applications/{application_id}/review', options)
          : client.POST('/v1/agent/credit-applications/{application_id}/close', options),
      );
    },
    onSuccess: (application: CreditApplicationView) => {
      queryClient.setQueryData(
        queryKeys.creditApplications.detail(application.application_id),
        application,
      );
      void queryClient.invalidateQueries({
        queryKey: [...queryKeys.creditApplications.all, 'list'],
      });
    },
  });
}
