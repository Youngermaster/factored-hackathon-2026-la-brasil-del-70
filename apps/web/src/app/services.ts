import type { QueryClient } from '@tanstack/react-query';

import { createSessionLossChannel, type SessionLossChannel } from '@/features/auth';
import {
  createApiClient,
  createQueryClient,
  type ApiClientOptions,
  type ApiContextValue,
} from '@/shared/api';
import { publishCspNonce } from '@/shared/lib/csp-nonce';

/** Everything the composition root wires once: the API client, the query client, and the session-loss channel. */
export interface AppServices {
  readonly api: ApiContextValue;
  readonly queryClient: QueryClient;
  readonly sessionLoss: SessionLossChannel;
}

export function createAppServices(
  options: Omit<ApiClientOptions, 'onUnauthorized'> = {},
): AppServices {
  // Before any dialog can inject a style element under the production CSP (shared/lib/csp-nonce.ts).
  publishCspNonce();
  const sessionLoss = createSessionLossChannel();
  return {
    api: createApiClient({ ...options, onUnauthorized: sessionLoss.report }),
    queryClient: createQueryClient(),
    sessionLoss,
  };
}
