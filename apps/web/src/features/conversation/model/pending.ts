/**
 * Local state of the chat: the customer's own messages still in flight or failed (optimistic rendering applies to
 * them only), and notices the client adds itself (a cancelled step-up). Settled turns live in the query cache.
 */
export interface PendingTurn {
  readonly turnId: string;
  readonly text: string;
  readonly status: 'sending' | 'failed';
  readonly error: unknown;
}

export type LocalNoticeCode = 'step_up_cancelled';

export interface LocalNotice {
  readonly id: string;
  readonly code: LocalNoticeCode;
  /** The turn the notice follows. */
  readonly afterTurnId: string;
}

export interface ChatState {
  readonly pending: readonly PendingTurn[];
  readonly notices: readonly LocalNotice[];
}

export type ChatAction =
  | { readonly type: 'sent'; readonly turnId: string; readonly text: string }
  | { readonly type: 'failed'; readonly turnId: string; readonly error: unknown }
  | { readonly type: 'retrying'; readonly turnId: string }
  | { readonly type: 'settled'; readonly turnId: string }
  | { readonly type: 'notice'; readonly notice: LocalNotice }
  | { readonly type: 'reset' };

export const initialChatState: ChatState = { pending: [], notices: [] };

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case 'sent':
      return {
        ...state,
        pending: [
          ...state.pending,
          { turnId: action.turnId, text: action.text, status: 'sending', error: null },
        ],
      };
    case 'failed':
      return {
        ...state,
        pending: state.pending.map((turn) =>
          turn.turnId === action.turnId ? { ...turn, status: 'failed', error: action.error } : turn,
        ),
      };
    case 'retrying':
      return {
        ...state,
        pending: state.pending.map((turn) =>
          turn.turnId === action.turnId ? { ...turn, status: 'sending', error: null } : turn,
        ),
      };
    case 'settled':
      return { ...state, pending: state.pending.filter((turn) => turn.turnId !== action.turnId) };
    case 'notice':
      return { ...state, notices: [...state.notices, action.notice] };
    case 'reset':
      return initialChatState;
  }
}
