import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { axe } from '@/test/axe';
import { renderApp } from '@/test/app';
import { sessionView } from '@/test/msw/api';
import { startAuthServer } from '@/test/msw/auth';

// Whole pages: landmarks and headings are checked too (the component tests switch the region rule off).
const pageRules = { rules: { region: { enabled: true } } };

beforeEach(() => {
  vi.stubEnv('VITE_DEMO_MODE', 'true');
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe.each(['light', 'dark'] as const)('accessibility in the %s theme', (theme) => {
  it('sign-in, persona step', async () => {
    startAuthServer();
    renderApp({ path: '/login', theme });
    await screen.findByRole('heading', { level: 1, name: 'Ingresa a tu banca' });
    expect(document.documentElement).toHaveAttribute('data-theme', theme);
    expect(await axe(document.body, pageRules)).toHaveNoViolations();
  });

  it('sign-in, document step', async () => {
    startAuthServer();
    renderApp({ path: '/login', theme });
    await userEvent.click(await screen.findByRole('tab', { name: 'Documento' }));
    await userEvent.click(screen.getByRole('button', { name: 'Enviar código' }));
    expect(await axe(document.body, pageRules)).toHaveNoViolations();
  });

  it('sign-in, code step with the expired-session notice', async () => {
    startAuthServer();
    renderApp({ path: '/login?reason=expired&next=%2F', theme });
    expect(await screen.findByRole('alert')).toHaveTextContent('Tu sesión terminó');
    await userEvent.click(screen.getByRole('button', { name: /Dos tarjetas activas/ }));
    await screen.findByRole('textbox', { name: 'Código de verificación' });
    expect(await axe(document.body, pageRules)).toHaveNoViolations();
  });

  it('customer layout with the step-up dialog open', async () => {
    startAuthServer({ session: sessionView() });
    renderApp({ path: '/', theme });
    await screen.findByRole('heading', { level: 1, name: '¿En qué te ayudamos hoy?' });
    expect(await axe(document.body, pageRules)).toHaveNoViolations();

    await userEvent.click(screen.getByRole('button', { name: 'Confirmar identidad' }));
    const dialog = await screen.findByRole('dialog');
    await within(dialog).findByRole('textbox', { name: 'Código de verificación' });
    expect(await axe(dialog)).toHaveNoViolations();
  });

  it('console layout', async () => {
    startAuthServer({ session: sessionView({ role: 'agent' }) });
    renderApp({ path: '/console', theme });
    await screen.findByRole('heading', { level: 1, name: 'Resumen' });
    expect(await axe(document.body, pageRules)).toHaveNoViolations();
  });

  it('preferences sheet', async () => {
    startAuthServer();
    renderApp({ path: '/login', theme });
    await userEvent.click(await screen.findByRole('button', { name: 'Preferencias' }));
    const sheet = await screen.findByRole('dialog', { name: 'Preferencias' });
    expect(within(sheet).getByRole('combobox', { name: 'Tema' })).toBeInTheDocument();
    expect(await axe(sheet)).toHaveNoViolations();
  });
});

describe('landmarks and keyboard entry', () => {
  it('offers a skip link to the main content first', async () => {
    startAuthServer({ session: sessionView() });
    renderApp({ path: '/' });
    await screen.findByRole('heading', { level: 1 });
    await userEvent.tab();
    const skip = screen.getByRole('link', { name: 'Saltar al contenido' });
    expect(skip).toHaveFocus();
    expect(skip).toHaveAttribute('href', '#main');
    expect(screen.getByRole('main')).toHaveAttribute('id', 'main');
    expect(screen.getByRole('banner')).toBeInTheDocument();
  });
});
