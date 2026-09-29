import { createContext, use } from 'react';

/** Where a selection came from: the chat (a message) or the glass box (a trace entry). */
export type SelectionSource = 'message' | 'trace';

export interface TurnSelection {
  /** The selected turn id, or null when nothing is selected. */
  readonly turnId: string | null;
  readonly source: SelectionSource | null;
  readonly select: (turnId: string | null, source: SelectionSource) => void;
}

export const TurnSelectionContext = createContext<TurnSelection | null>(null);

/**
 * The turn selected in the chat or the glass box. Selecting a message highlights its trace entry and the reverse.
 * Outside a <TurnSelectionProvider> nothing is selectable (a stand-alone trace, a test of one part).
 */
export function useTurnSelection(): TurnSelection | null {
  return use(TurnSelectionContext);
}
