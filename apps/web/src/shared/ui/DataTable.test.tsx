import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { axe } from '@/test/axe';
import { renderWithProviders } from '@/test/render';

import * as DataTable from './DataTable';
import { useTableSort } from './use-table-sort';

interface Row {
  readonly id: string;
  readonly merchant: string;
  readonly amount: number;
}

const rows: Row[] = [
  { id: 't1', merchant: 'Farmacia Central', amount: 320 },
  { id: 't2', merchant: 'Aerolínea Sur', amount: 4100 },
  { id: 't3', merchant: 'Café Norte', amount: 85 },
];

const compare = (a: Row, b: Row, key: 'merchant' | 'amount') =>
  key === 'amount' ? a.amount - b.amount : a.merchant.localeCompare(b.merchant);

function Transactions() {
  const table = useTableSort<Row, 'merchant' | 'amount'>(
    rows,
    { key: 'merchant', direction: 'ascending' },
    compare,
  );
  return (
    <DataTable.Root caption="Movimientos recientes">
      <DataTable.Head>
        <tr>
          <DataTable.HeaderCell
            sort={table.directionOf('merchant')}
            onSort={() => {
              table.sortBy('merchant');
            }}
          >
            Comercio
          </DataTable.HeaderCell>
          <DataTable.HeaderCell
            numeric
            sort={table.directionOf('amount')}
            onSort={() => {
              table.sortBy('amount');
            }}
          >
            Monto
          </DataTable.HeaderCell>
          <DataTable.HeaderCell>Id</DataTable.HeaderCell>
        </tr>
      </DataTable.Head>
      <DataTable.Body>
        {table.rows.map((row) => (
          <DataTable.Row key={row.id}>
            <DataTable.Cell>{row.merchant}</DataTable.Cell>
            <DataTable.Cell numeric>{row.amount}</DataTable.Cell>
            <DataTable.Cell>{row.id}</DataTable.Cell>
          </DataTable.Row>
        ))}
      </DataTable.Body>
    </DataTable.Root>
  );
}

const firstColumn = () =>
  screen
    .getAllByRole('row')
    .slice(1)
    .map((row) => within(row).getAllByRole('cell')[0]?.textContent);

describe('DataTable', () => {
  it('names its scrollable region with the caption (regression: two tables had unnamed, duplicate regions)', () => {
    renderWithProviders(<Transactions />);
    expect(screen.getByRole('region', { name: 'Movimientos recientes' })).toBeInTheDocument();
  });

  it('is named by its caption and marks the sorted column', async () => {
    const { container } = renderWithProviders(<Transactions />);
    expect(screen.getByRole('table', { name: 'Movimientos recientes' })).toBeInTheDocument();
    const [merchant, amount, id] = screen.getAllByRole('columnheader');
    expect(merchant).toHaveAttribute('aria-sort', 'ascending');
    expect(amount).toHaveAttribute('aria-sort', 'none');
    expect(id).not.toHaveAttribute('aria-sort');
    expect(firstColumn()).toEqual(['Aerolínea Sur', 'Café Norte', 'Farmacia Central']);
    expect(await axe(container)).toHaveNoViolations();
  });

  it('sorts by another column, then flips the direction', async () => {
    renderWithProviders(<Transactions />);
    await userEvent.click(screen.getByRole('button', { name: /Monto/ }));
    expect(screen.getAllByRole('columnheader')[1]).toHaveAttribute('aria-sort', 'ascending');
    expect(firstColumn()).toEqual(['Café Norte', 'Farmacia Central', 'Aerolínea Sur']);

    await userEvent.click(screen.getByRole('button', { name: /Monto/ }));
    expect(screen.getAllByRole('columnheader')[1]).toHaveAttribute('aria-sort', 'descending');
    expect(firstColumn()).toEqual(['Aerolínea Sur', 'Farmacia Central', 'Café Norte']);
  });
});
