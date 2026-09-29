import { createContext, use, type RefObject } from 'react';

import type { Language } from '@/shared/i18n';

import type { ConversationView, TurnView } from '../api/conversation';
import type { LocalNotice, PendingTurn } from './pending';
import type { QuickReply } from './replies';

export type LoadStatus = 'new' | 'loading' | 'ready' | 'not_found' | 'error';

export interface ConversationContextValue {
  readonly conversationId: string | null;
  readonly conversation: ConversationView | null;
  readonly turns: readonly TurnView[];
  readonly pending: readonly PendingTurn[];
  readonly notices: readonly LocalNotice[];
  readonly loadStatus: LoadStatus;
  readonly loadError: unknown;
  readonly reload: () => void;
  /** True while a message is on its way; the composer and the quick replies wait. */
  readonly inFlight: boolean;
  /** The latest settled turn: only its interactive parts are enabled. */
  readonly latestTurnId: string | null;
  /** The conversation's language (latest turn), or null before the first answer. */
  readonly language: Language | null;
  readonly send: (text: string) => void;
  readonly reply: (reply: QuickReply) => void;
  readonly retry: (turnId: string) => void;
  readonly stepUpAgain: () => void;
  readonly startNew: () => void;
  readonly composerRef: RefObject<HTMLTextAreaElement | null>;
  /** The composer's text, so a starter can fill it without sending. */
  readonly draft: string;
  readonly setDraft: (text: string) => void;
}

export const ConversationContext = createContext<ConversationContextValue | null>(null);

/** The conversation's state and actions, for the parts of <Conversation.Root>. */
export function useConversation(): ConversationContextValue {
  const context = use(ConversationContext);
  if (context === null) {
    throw new Error('Conversation parts must be inside <Conversation.Root>');
  }
  return context;
}

export const MAX_MESSAGE_LENGTH = 2000;
