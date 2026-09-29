import type { ApiError } from '@/shared/api';

export type SessionLossListener = (error: ApiError) => void;

/**
 * Connects the API client (created before the router exists) to the auth provider (inside the router, where it
 * can navigate). The client reports a lost session; the provider decides what the user sees.
 */
export interface SessionLossChannel {
  readonly report: (error: ApiError) => void;
  readonly subscribe: (listener: SessionLossListener) => () => void;
}

export function createSessionLossChannel(): SessionLossChannel {
  const listeners = new Set<SessionLossListener>();
  return {
    report: (error) => {
      listeners.forEach((listener) => {
        listener(error);
      });
    },
    subscribe: (listener) => {
      listeners.add(listener);
      return () => {
        listeners.delete(listener);
      };
    },
  };
}
