import { createContext, use } from 'react';

import type { ApiContextValue } from './client';

export const ApiContext = createContext<ApiContextValue | null>(null);

/** The typed API client and its CSRF store, provided once by the app composition root. */
export function useApi(): ApiContextValue {
  const context = use(ApiContext);
  if (context === null) {
    throw new Error('useApi must be used inside <ApiProvider>');
  }
  return context;
}
