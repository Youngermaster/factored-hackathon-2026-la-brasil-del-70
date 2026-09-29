import { skipToken, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { queryKeys, unwrap, useApi, type Schema } from '@/shared/api';

export type ConversationHistory = Schema<'ConversationHistoryResponse'>;
export type ConversationView = Schema<'ConversationView'>;
export type TurnView = Schema<'TurnView'>;
export type TurnResponse = Schema<'TurnResponse'>;
export type AssistantMessage = Schema<'AssistantMessage'>;

/** The conversation's turns from `GET /v1/conversations/{id}`; idle until there is an id. */
export function useConversationHistory(conversationId: string | null) {
  const { client } = useApi();
  return useQuery({
    queryKey: queryKeys.conversations.detail(conversationId ?? ''),
    queryFn:
      conversationId === null
        ? skipToken
        : () =>
            unwrap(
              client.GET('/v1/conversations/{conversation_id}', {
                params: { path: { conversation_id: conversationId } },
              }),
            ),
  });
}

/** Opens a conversation and seeds its (empty) history, so the page does not fetch what it already knows. */
export function useCreateConversation() {
  const { client } = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => unwrap(client.POST('/v1/conversations')),
    onSuccess: (conversation) => {
      queryClient.setQueryData<ConversationHistory>(
        queryKeys.conversations.detail(conversation.conversation_id),
        { conversation, turns: [] },
      );
    },
  });
}

export interface SendTurnInput {
  readonly conversationId: string;
  readonly turnId: string;
  readonly text: string;
}

/**
 * Sends one customer message. The turn id is made by the client, so resending the same input after a network
 * failure replays the stored result instead of running the turn twice. On success the turn is appended to the
 * cached history and the trace is marked stale.
 */
export function useSendTurn() {
  const { client } = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ conversationId, turnId, text }: SendTurnInput) =>
      unwrap(
        client.POST('/v1/conversations/{conversation_id}/turns', {
          params: { path: { conversation_id: conversationId } },
          body: { turn_id: turnId, text },
        }),
      ),
    onSuccess: (response, { conversationId, text }) => {
      queryClient.setQueryData<ConversationHistory>(
        queryKeys.conversations.detail(conversationId),
        (history) => (history === undefined ? history : appendTurn(history, response, text)),
      );
      void queryClient.invalidateQueries({
        queryKey: queryKeys.conversations.trace(conversationId),
      });
    },
  });
}

/** The history after one more turn: the turn itself, and where the conversation now is. Replays change nothing. */
export function appendTurn(
  history: ConversationHistory,
  response: TurnResponse,
  text: string,
  now: Date = new Date(),
): ConversationHistory {
  if (history.turns.some((turn) => turn.turn_id === response.turn_id)) {
    return history;
  }
  const at = now.toISOString();
  const last = history.turns.at(-1)?.sequence ?? 0;
  const turn: TurnView = {
    turn_id: response.turn_id,
    sequence: last + 1,
    customer_text: text,
    language: response.message.language,
    message: response.message,
    received_at: at,
    completed_at: at,
  };
  const status = response.outcome === 'escalated' ? 'escalated' : history.conversation.status;
  return {
    conversation: {
      ...history.conversation,
      state: response.state,
      status,
      language: response.message.language,
      updated_at: at,
      ...(response.workflow === null ? {} : { workflow: response.workflow }),
    },
    turns: [...history.turns, turn],
  };
}
