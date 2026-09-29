import type { ReactNode } from 'react';

import type { ApiContextValue } from './client';
import { ApiContext } from './context';

export function ApiProvider({
  value,
  children,
}: {
  readonly value: ApiContextValue;
  readonly children: ReactNode;
}) {
  return <ApiContext value={value}>{children}</ApiContext>;
}
