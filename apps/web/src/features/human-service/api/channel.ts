import { useEffect } from 'react';
import {
  useInfiniteQuery,
  useMutation,
  useQueryClient,
  type InfiniteData,
} from '@tanstack/react-query';

import { queryKeys, unwrap, useApi, type Schema } from '@/shared/api';

export type HumanServiceView = Schema<'HumanServiceResponse'>;
export type HumanMessage = Schema<'HumanMessage'>;
export type ChannelSide = 'customer' | 'agent';

/** Persisted pages are refetched after reconnect; a failed transport never changes the handoff lifecycle. */
export function useHumanChannel(side: ChannelSide, id: string | null) {
  const { client } = useApi();
  const query = useInfiniteQuery({
    queryKey: queryKeys.humanService.detail(side, id ?? ''),
    enabled: id !== null,
    initialPageParam: 0,
    queryFn: ({ pageParam }) => {
      if (id === null) throw new Error('Human service requires an identifier');
      return side === 'customer'
        ? unwrap(
            client.GET('/v1/conversations/{conversation_id}/human-service', {
              params: { path: { conversation_id: id }, query: { after: pageParam } },
            }),
          )
        : unwrap(
            client.GET('/v1/agent/handoffs/{handoff_id}/human-service', {
              params: { path: { handoff_id: id }, query: { after: pageParam } },
            }),
          );
    },
    getNextPageParam: (page) =>
      page.messages.length === 100 ? page.messages.at(-1)?.sequence : undefined,
    staleTime: 0,
    refetchInterval: (state) =>
      state.state.data?.pages.at(-1)?.status === 'closed' ? false : 2000,
  });
  const { hasNextPage, isFetching, isFetchNextPageError, fetchNextPage } = query;
  useEffect(() => {
    if (hasNextPage && !isFetching && !isFetchNextPageError) void fetchNextPage();
  }, [hasNextPage, isFetching, isFetchNextPageError, fetchNextPage]);
  const view = query.data?.pages.at(-1) ?? null;
  const messages = [
    ...new Map(
      (query.data?.pages.flatMap((page) => page.messages) ?? []).map((message) => [
        message.message_id,
        message,
      ]),
    ).values(),
  ].sort((a, b) => a.sequence - b.sequence);
  return { ...query, view, messages };
}

export interface HumanSendInput {
  readonly id: string;
  readonly messageId: string;
  readonly text: string;
}

export function useSendHumanMessage(side: ChannelSide) {
  const { client } = useApi();
  const cache = useQueryClient();
  return useMutation({
    mutationFn: ({ id, messageId, text }: HumanSendInput) => {
      const body = { message_id: messageId, text };
      return side === 'customer'
        ? unwrap(
            client.POST('/v1/conversations/{conversation_id}/human-service/messages', {
              params: { path: { conversation_id: id } },
              body,
            }),
          )
        : unwrap(
            client.POST('/v1/agent/handoffs/{handoff_id}/human-service/messages', {
              params: { path: { handoff_id: id } },
              body,
            }),
          );
    },
    onSuccess: (receipt, { id }) => {
      const key = queryKeys.humanService.detail(side, id);
      cache.setQueryData<InfiniteData<HumanServiceView>>(key, (data) => {
        if (
          data === undefined ||
          data.pages.some((page) =>
            page.messages.some((m) => m.message_id === receipt.message.message_id),
          )
        )
          return data;
        return {
          ...data,
          pages: data.pages.map((page, index) =>
            index === data.pages.length - 1
              ? { ...page, messages: [...page.messages, receipt.message] }
              : page,
          ),
        };
      });
      void cache.invalidateQueries({ queryKey: key });
    },
  });
}
