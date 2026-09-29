import { useCallback, useMemo, useState, type ReactNode } from 'react';

import { TurnSelectionContext, type SelectionSource } from './context';

/**
 * Page-level linked selection between the chat and the glass box. The page provides it; both features read it, so
 * neither feature owns the other and nothing is global.
 */
export function TurnSelectionProvider({ children }: { readonly children: ReactNode }) {
  const [state, setState] = useState<{
    turnId: string | null;
    source: SelectionSource | null;
  }>({ turnId: null, source: null });
  const select = useCallback((turnId: string | null, source: SelectionSource) => {
    setState({ turnId, source: turnId === null ? null : source });
  }, []);
  const value = useMemo(() => ({ ...state, select }), [state, select]);
  return <TurnSelectionContext value={value}>{children}</TurnSelectionContext>;
}
