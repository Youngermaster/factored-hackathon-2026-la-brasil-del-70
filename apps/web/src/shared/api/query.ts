import { QueryClient } from '@tanstack/react-query';

import { ApiError, NetworkError } from './problem';

/** Default freshness for server data; screens that need live data set their own. */
export const DEFAULT_STALE_TIME_MS = 30_000;
const MAX_RETRIES = 2;

/** Retry only what can succeed on its own: network failures and 5xx. A 4xx is an answer, never retried. */
export function shouldRetry(failureCount: number, error: unknown): boolean {
  if (failureCount >= MAX_RETRIES) {
    return false;
  }
  if (error instanceof NetworkError) {
    return true;
  }
  return error instanceof ApiError && error.status >= 500;
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: DEFAULT_STALE_TIME_MS,
        retry: shouldRetry,
        refetchOnWindowFocus: true,
      },
      // Writes are never retried automatically: the API makes turns idempotent, but the user decides to resend.
      mutations: { retry: false },
    },
  });
}

/**
 * Query keys, built in one place so invalidation matches what was cached. Every key starts with 'api'; a family
 * key (for example `queryKeys.conversations.all`) invalidates every key below it.
 */
export const queryKeys = {
  all: ['api'] as const,
  auth: {
    all: ['api', 'auth'] as const,
    session: () => ['api', 'auth', 'session'] as const,
  },
  conversations: {
    all: ['api', 'conversations'] as const,
    detail: (conversationId: string) => ['api', 'conversations', conversationId] as const,
    trace: (conversationId: string) => ['api', 'conversations', conversationId, 'trace'] as const,
  },
  assistantProfile: {
    all: ['api', 'assistant-profile'] as const,
    detail: (conversationId: string) => ['api', 'assistant-profile', conversationId] as const,
  },
  handoffs: {
    all: ['api', 'handoffs'] as const,
    list: (filters: Readonly<Record<string, string | undefined>> = {}) =>
      ['api', 'handoffs', 'list', filters] as const,
    detail: (handoffId: string) => ['api', 'handoffs', handoffId] as const,
  },
  creditApplications: {
    all: ['api', 'credit-applications'] as const,
    detail: (applicationId: string) => ['api', 'credit-applications', applicationId] as const,
  },
  evaluation: {
    all: ['api', 'evaluation'] as const,
    summaries: () => ['api', 'evaluation', 'summaries'] as const,
    trace: (conversationId: string) => ['api', 'evaluation', 'trace', conversationId] as const,
  },
} as const;
