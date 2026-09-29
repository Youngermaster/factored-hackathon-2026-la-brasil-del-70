import { skipToken, useQuery } from '@tanstack/react-query';

import { queryKeys, unwrap, useApi, type Schema } from '@/shared/api';

export type CustomerTraceRecord = Schema<'CustomerTraceRecord'>;
export type StaffTraceRecord = Schema<'StaffTraceRecord'>;
export type TraceRecord = CustomerTraceRecord | StaffTraceRecord;

/** The customer's view of a conversation's execution records: no estimate values, no defenses. */
export function useCustomerTrace(conversationId: string | null) {
  const { client } = useApi();
  return useQuery({
    queryKey: queryKeys.conversations.trace(conversationId ?? ''),
    queryFn:
      conversationId === null
        ? skipToken
        : () =>
            unwrap(
              client.GET('/v1/conversations/{conversation_id}/trace', {
                params: { path: { conversation_id: conversationId } },
              }),
            ),
  });
}

/** The evaluator's view: everything in the record, the internal risk estimates included. */
export function useStaffTrace(conversationId: string | null) {
  const { client } = useApi();
  return useQuery({
    queryKey: queryKeys.evaluation.trace(conversationId ?? ''),
    queryFn:
      conversationId === null
        ? skipToken
        : () =>
            unwrap(
              client.GET('/v1/eval/conversations/{conversation_id}/trace', {
                params: { path: { conversation_id: conversationId } },
              }),
            ),
    retry: false,
  });
}

/**
 * The clause excerpts each turn cited, from the customer's own history (the same cache entry the chat uses). The
 * trace has clause ids only; this keeps one source of clause text in the browser.
 */
export function useCitedExcerpts(conversationId: string | null, enabled: boolean) {
  const { client } = useApi();
  const history = useQuery({
    queryKey: queryKeys.conversations.detail(conversationId ?? ''),
    queryFn:
      conversationId === null || !enabled
        ? skipToken
        : () =>
            unwrap(
              client.GET('/v1/conversations/{conversation_id}', {
                params: { path: { conversation_id: conversationId } },
              }),
            ),
  });
  const excerpts = new Map<string, Map<string, string>>();
  for (const turn of history.data?.turns ?? []) {
    excerpts.set(
      turn.turn_id,
      new Map(
        (turn.message?.citations ?? []).map((citation) => [citation.clause, citation.excerpt]),
      ),
    );
  }
  return excerpts;
}
