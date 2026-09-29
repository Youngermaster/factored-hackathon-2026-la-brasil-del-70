import type { QueryClient } from '@tanstack/react-query';

import { queryKeys } from '@/shared/api';

import type { SessionView } from '../api/session';

/**
 * Drops every cached server record except the session entry, then sets the session. Used when the identity
 * changes (sign-in, sign-out, a lost session), so nothing cached for one person is shown to the next. The session
 * entry is updated in place rather than removed, because the route guards observe it.
 */
export function replaceSession(queryClient: QueryClient, session: SessionView | null): void {
  const sessionKey = queryKeys.auth.session();
  queryClient.removeQueries({
    queryKey: queryKeys.all,
    predicate: (query) => JSON.stringify(query.queryKey) !== JSON.stringify(sessionKey),
  });
  queryClient.setQueryData(sessionKey, session);
}
