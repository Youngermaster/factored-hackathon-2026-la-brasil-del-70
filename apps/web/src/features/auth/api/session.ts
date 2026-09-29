import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';

import { ApiError, queryKeys, unwrap, useApi, type Schema } from '@/shared/api';

import { replaceSession } from '../model/cache';

export type SessionView = Schema<'SessionView'>;
export type Challenge = Schema<'ChallengeResponse'>;
export type LoginIdentification = Schema<'PersonaLogin'> | Schema<'DocumentLogin'>;

/**
 * The current session from `GET /v1/auth/me`, or null when signed out. It is the source of truth for route guards,
 * so it is never considered fresh (staleTime 0) and refetches when the window regains focus.
 */
export function useSession() {
  const { client } = useApi();
  return useQuery({
    queryKey: queryKeys.auth.session(),
    queryFn: async (): Promise<SessionView | null> => {
      try {
        return await unwrap(client.GET('/v1/auth/me'));
      } catch (error) {
        if (error instanceof ApiError && error.status === 401) {
          return null;
        }
        throw error;
      }
    },
    staleTime: 0,
  });
}

export function useStartLogin() {
  const { client } = useApi();
  return useMutation({
    mutationFn: (identification: LoginIdentification) =>
      unwrap(client.POST('/v1/auth/start', { body: identification })),
  });
}

export function useVerifyLogin() {
  const { client } = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: Schema<'VerifyLoginRequest'>) =>
      unwrap(client.POST('/v1/auth/verify', { body: input })),
    onSuccess: ({ session }) => {
      // A new identity: nothing cached for the previous one may leak into this session.
      replaceSession(queryClient, session);
    },
  });
}

/** Revokes the session on the server. The caller leaves the guarded page, then clears the cache (see LogoutButton). */
export function useLogout() {
  const { client } = useApi();
  return useMutation({
    mutationFn: () => unwrap(client.POST('/v1/auth/logout')),
  });
}

export function useStartStepUp() {
  const { client } = useApi();
  return useMutation({
    mutationFn: () => unwrap(client.POST('/v1/auth/step-up/start')),
  });
}

export function useVerifyStepUp() {
  const { client } = useApi();
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: Schema<'VerifyStepUpRequest'>) =>
      unwrap(client.POST('/v1/auth/step-up/verify', { body: input })),
    onSuccess: ({ session }) => {
      queryClient.setQueryData(queryKeys.auth.session(), session);
    },
  });
}
