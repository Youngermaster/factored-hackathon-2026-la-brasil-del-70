import { screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { axe } from '@/test/axe';
import { renderWithProviders } from '@/test/render';

import { Button } from './Button';
import * as Dialog from './Dialog';
import * as Sheet from './Sheet';

function ConfirmDialog() {
  return (
    <Dialog.Root>
      <Dialog.Trigger asChild>
        <Button>Bloquear tarjeta</Button>
      </Dialog.Trigger>
      <Dialog.Content>
        <Dialog.Header>
          <Dialog.Title>Confirma el bloqueo</Dialog.Title>
          <Dialog.Description>La tarjeta terminada en 4821 dejará de funcionar.</Dialog.Description>
        </Dialog.Header>
        <label htmlFor="motivo">Motivo</label>
        <input id="motivo" />
        <Dialog.Footer>
          <Dialog.Close asChild>
            <Button variant="secondary">Cancelar</Button>
          </Dialog.Close>
        </Dialog.Footer>
      </Dialog.Content>
    </Dialog.Root>
  );
}

describe('Dialog', () => {
  it('moves focus in, traps it, closes on Escape, and returns focus to the trigger', async () => {
    renderWithProviders(<ConfirmDialog />);
    const trigger = screen.getByRole('button', { name: 'Bloquear tarjeta' });
    await userEvent.click(trigger);

    const dialog = await screen.findByRole('dialog', { name: 'Confirma el bloqueo' });
    expect(dialog).toHaveAccessibleDescription('La tarjeta terminada en 4821 dejará de funcionar.');
    expect(dialog).toContainElement(document.activeElement as HTMLElement);

    for (let step = 0; step < 5; step += 1) {
      await userEvent.tab();
      expect(dialog).toContainElement(document.activeElement as HTMLElement);
    }

    await userEvent.keyboard('{Escape}');
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull();
    });
    expect(trigger).toHaveFocus();
  });

  it('has a labeled close button and no axe violations', async () => {
    renderWithProviders(<ConfirmDialog />);
    await userEvent.click(screen.getByRole('button', { name: 'Bloquear tarjeta' }));
    const dialog = await screen.findByRole('dialog');
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeInTheDocument();
    expect(await axe(dialog)).toHaveNoViolations();
  });
});

describe('Sheet', () => {
  it('opens as a dialog, traps focus, and closes with its close button', async () => {
    renderWithProviders(
      <Sheet.Root>
        <Sheet.Trigger asChild>
          <Button>Menú</Button>
        </Sheet.Trigger>
        <Sheet.Content aria-describedby={undefined}>
          <Sheet.Title>Preferencias</Sheet.Title>
          <a href="/inicio">Inicio</a>
        </Sheet.Content>
      </Sheet.Root>,
    );
    const trigger = screen.getByRole('button', { name: 'Menú' });
    await userEvent.click(trigger);
    const sheet = await screen.findByRole('dialog', { name: 'Preferencias' });
    expect(sheet).toContainElement(document.activeElement as HTMLElement);
    await userEvent.click(screen.getByRole('button', { name: 'Cerrar' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull();
    });
    expect(trigger).toHaveFocus();
  });
});
