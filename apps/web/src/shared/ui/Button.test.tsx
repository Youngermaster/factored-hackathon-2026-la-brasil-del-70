import { screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it, vi } from 'vitest';

import { renderWithProviders } from '@/test/render';

import { Button } from './Button';
import { IconButton } from './IconButton';
import { CloseIcon } from './icons';
import { TextLink } from './TextLink';

describe('Button', () => {
  it('is a button that activates with the keyboard', async () => {
    const onClick = vi.fn();
    renderWithProviders(<Button onClick={onClick}>Guardar</Button>);
    const button = screen.getByRole('button', { name: 'Guardar' });
    expect(button).toHaveAttribute('type', 'button');
    button.focus();
    await userEvent.keyboard('{Enter}');
    await userEvent.keyboard(' ');
    expect(onClick).toHaveBeenCalledTimes(2);
  });

  it('announces a pending action and ignores clicks while it runs', async () => {
    const onClick = vi.fn();
    renderWithProviders(
      <Button pending onClick={onClick}>
        Enviar
      </Button>,
    );
    const button = screen.getByRole('button', { name: 'Enviar' });
    expect(button).toHaveAttribute('aria-busy', 'true');
    expect(button).toHaveAttribute('aria-disabled', 'true');
    await userEvent.click(button);
    expect(onClick).not.toHaveBeenCalled();
  });

  it('renders its child with button styles when asChild is set', () => {
    renderWithProviders(
      <Button asChild variant="secondary">
        <a href="/inicio">Inicio</a>
      </Button>,
    );
    const link = screen.getByRole('link', { name: 'Inicio' });
    expect(link).not.toHaveAttribute('type');
    expect(link.className).toContain('border-border-strong');
  });
});

describe('IconButton', () => {
  it('has the label as its accessible name and hides the icon', () => {
    renderWithProviders(<IconButton label="Cerrar" icon={<CloseIcon />} />);
    const button = screen.getByRole('button', { name: 'Cerrar' });
    expect(button.querySelector('[aria-hidden="true"]')).not.toBeNull();
  });
});

describe('TextLink', () => {
  it('opens external links in a new tab without an opener and says so', () => {
    renderWithProviders(
      <TextLink href="https://example.org" external>
        Política
      </TextLink>,
    );
    const link = screen.getByRole('link', { name: /Política/ });
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', 'noopener noreferrer');
    expect(link).toHaveTextContent('se abre en una pestaña nueva');
  });

  it('keeps internal links in the same tab', () => {
    renderWithProviders(<TextLink href="/ayuda">Ayuda</TextLink>);
    expect(screen.getByRole('link', { name: 'Ayuda' })).not.toHaveAttribute('target');
  });
});
