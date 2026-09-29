import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { renderWithProviders } from '@/test/render';

import * as Tabs from './Tabs';

describe('Tabs', () => {
  it('moves between tabs with the arrow keys and shows the selected panel', async () => {
    renderWithProviders(
      <Tabs.Root defaultValue="persona">
        <Tabs.List aria-label="Forma de ingreso">
          <Tabs.Trigger value="persona">Perfil</Tabs.Trigger>
          <Tabs.Trigger value="document">Documento</Tabs.Trigger>
        </Tabs.List>
        <Tabs.Panel value="persona">Perfiles de demostración</Tabs.Panel>
        <Tabs.Panel value="document">Datos del documento</Tabs.Panel>
      </Tabs.Root>,
    );
    expect(screen.getByRole('tablist', { name: 'Forma de ingreso' })).toBeInTheDocument();
    const persona = screen.getByRole('tab', { name: 'Perfil' });
    expect(persona).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Perfiles de demostración');

    persona.focus();
    await userEvent.keyboard('{ArrowRight}');
    const document = screen.getByRole('tab', { name: 'Documento' });
    expect(document).toHaveFocus();
    expect(document).toHaveAttribute('aria-selected', 'true');
    expect(screen.getByRole('tabpanel')).toHaveTextContent('Datos del documento');
  });
});
