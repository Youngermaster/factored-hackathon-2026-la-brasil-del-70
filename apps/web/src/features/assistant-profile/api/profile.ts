import { skipToken, useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { queryKeys, unwrap, useApi, type Schema } from '@/shared/api';

export type AssistantProfile = Schema<'AssistantProfileView'>;

/** A profile belongs to the customer; the conversation id authorizes each read and write. */
export function useAssistantProfile(conversationId: string | null) {
  const { client } = useApi();
  return useQuery({
    queryKey: queryKeys.assistantProfile.detail(conversationId ?? ''),
    queryFn:
      conversationId === null
        ? skipToken
        : () =>
            unwrap(
              client.GET('/v1/conversations/{conversation_id}/assistant-profile', {
                params: { path: { conversation_id: conversationId } },
              }),
            ),
    placeholderData: (previous) => previous,
  });
}

export function useChangeAssistantName() {
  const { client } = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ conversationId, name }: { conversationId: string; name: string }) =>
      unwrap(
        client.POST('/v1/conversations/{conversation_id}/assistant-profile/name', {
          params: { path: { conversation_id: conversationId } },
          body: { name },
        }),
      ),
    onSuccess: (profile, { conversationId }) => {
      queryClient.setQueryData(queryKeys.assistantProfile.detail(conversationId), profile);
    },
  });
}

export function useChangeAssistantImage() {
  const { client } = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (conversationId: string) =>
      unwrap(
        client.POST('/v1/conversations/{conversation_id}/assistant-profile/mock-image', {
          params: { path: { conversation_id: conversationId } },
        }),
      ),
    onSuccess: (profile, conversationId) => {
      queryClient.setQueryData(queryKeys.assistantProfile.detail(conversationId), profile);
    },
  });
}
