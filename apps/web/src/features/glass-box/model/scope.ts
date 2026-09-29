import { createContext, use } from 'react';

import type { TraceRecord } from '../api/trace';

export type TraceView = 'customer' | 'staff';

export interface RecordScope {
  readonly record: TraceRecord;
  readonly view: TraceView;
  /** The turn's cited clause excerpts by `clause_id@version` (empty for the staff view, which has no history). */
  readonly excerpts: ReadonlyMap<string, string>;
}

export const RecordContext = createContext<RecordScope | null>(null);

/** The execution record a glass box section renders. */
export function useRecord(): RecordScope {
  const context = use(RecordContext);
  if (context === null) {
    throw new Error('Glass box sections must be inside a turn trace');
  }
  return context;
}
