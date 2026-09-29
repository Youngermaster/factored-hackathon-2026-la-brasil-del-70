import { useMemo, useState } from 'react';

import type { SortDirection } from './DataTable';

export interface TableSort<K extends string> {
  readonly key: K;
  readonly direction: SortDirection;
}

/**
 * Local sort state for a <DataTable>: clicking the sorted column flips the direction, another column sorts
 * ascending. `compare` receives the sort key; rows keep their order when it returns 0.
 */
export function useTableSort<Row, K extends string>(
  rows: readonly Row[],
  initial: TableSort<K>,
  compare: (a: Row, b: Row, key: K) => number,
) {
  const [sort, setSort] = useState<TableSort<K>>(initial);
  const sorted = useMemo(() => {
    const factor = sort.direction === 'ascending' ? 1 : -1;
    return [...rows].sort((a, b) => factor * compare(a, b, sort.key));
  }, [rows, sort, compare]);
  const sortBy = (key: K) => {
    setSort((current) =>
      current.key === key
        ? { key, direction: current.direction === 'ascending' ? 'descending' : 'ascending' }
        : { key, direction: 'ascending' },
    );
  };
  const directionOf = (key: K): SortDirection | null => (sort.key === key ? sort.direction : null);
  return { rows: sorted, sort, sortBy, directionOf };
}
