import type { QueryClient } from '@tanstack/react-query';

import { createSessionLossChannel, type SessionLossChannel } from '@/features/auth';
import {
  createApiClient,
  createQueryClient,
  type ApiClientOptions,
  type ApiContextValue,
} from '@/shared/api';

/** Everything the composition root wires once: the API client, the query client, and the session-loss channel. */
export interface AppServices {
  readonly api: ApiContextValue;
  readonly queryClient: QueryClient;
  readonly sessionLoss: SessionLossChannel;
}

export function createAppServices(
  options: Omit<ApiClientOptions, 'onUnauthorized'> = {},
): AppServices {
  const sessionLoss = createSessionLossChannel();
  return {
    api: createApiClient({ ...options, onUnauthorized: sessionLoss.report }),
    queryClient: createQueryClient(),
    sessionLoss,
  };
}
