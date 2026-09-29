import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { Button } from './Button';
import { useToast } from './toast-context';
import { Tooltip } from './Tooltip';

function Notifier() {
  const { notify } = useToast();
  return (
    <Button
      onClick={() => {
        notify({
          title: 'Identidad confirmada.',
          tone: 'decision',
          description: 'Puedes continuar.',
        });
      }}
    >
      Avisar
    </Button>
  );
}

describe('Toast', () => {
  it('shows a notice in a live region and dismisses it with the close button', async () => {
    renderWithProviders(<Notifier />);
    await userEvent.click(screen.getByRole('button', { name: 'Avisar' }));
    const status = await screen.findByText('Identidad confirmada.');
    expect(status).toBeVisible();
    expect(screen.getByText('Puedes continuar.')).toBeVisible();
    expect(screen.getByRole('region', { name: /Avisos/ })).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: 'Cerrar' }));
    await waitFor(() => {
      expect(screen.queryByText('Identidad confirmada.')).toBeNull();
    });
  });

  it('refuses to notify outside the provider', () => {
    vi.spyOn(console, 'error').mockImplementation(() => undefined);
    function Orphan() {
      useToast();
      return null;
    }
    expect(() => render(<Orphan />)).toThrow(/ToastProvider/);
  });
});

describe('Tooltip', () => {
  it('shows its content when the trigger gets keyboard focus', async () => {
    renderWithProviders(
      <Tooltip content="Preferencias">
        <button type="button" aria-label="Preferencias">
          P
        </button>
      </Tooltip>,
    );
    await userEvent.tab();
    expect(screen.getByRole('button', { name: 'Preferencias' })).toHaveFocus();
    expect(await screen.findByRole('tooltip')).toHaveTextContent('Preferencias');
  });
});
