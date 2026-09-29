import { createContext, use } from 'react';

import type { HandoffView } from '../api/handoffs';

export const HandoffContext = createContext<HandoffView | null>(null);

/** The handoff the detail sections and actions render, from the detail view's scope. */
export function useHandoffView(): HandoffView {
  const context = use(HandoffContext);
  if (context === null) {
    throw new Error('Handoff sections must be inside <HandoffDetail>');
  }
  return context;
}
