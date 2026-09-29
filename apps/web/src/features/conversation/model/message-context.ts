import { createContext, use } from 'react';

import type { AssistantMessage } from '../api/conversation';

export interface MessageScope {
  readonly turnId: string;
  readonly message: AssistantMessage;
  /** Buttons act only on the latest answered turn, and only while nothing is in flight. */
  readonly interactive: boolean;
}

export const MessageContext = createContext<MessageScope | null>(null);

/** The assistant message a part belongs to. */
export function useMessage(): MessageScope {
  const context = use(MessageContext);
  if (context === null) {
    throw new Error('Message parts must be inside an assistant message');
  }
  return context;
}
