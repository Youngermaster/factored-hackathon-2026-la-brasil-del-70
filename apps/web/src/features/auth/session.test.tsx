import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { currentPath, renderApp } from '@/test/app';
import { apiGet, problem, sessionView } from '@/test/msw/api';
import { DEMO_CODE, startAuthServer } from '@/test/msw/auth';
import { server } from '@/test/msw/server';

beforeEach(() => {
  vi.stubEnv('VITE_DEMO_MODE', 'true');
});

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('a session lost mid-way', () => {
  it('sends the customer to sign-in and back to the same conversation afterwards', async () => {
    const auth = startAuthServer({ session: sessionView() });
    const { router } = renderApp({ path: '/?conversation=c-123' });
    expect(await screen.findByText('Tu conversación c-123 sigue abierta.')).toBeInTheDocument();

    auth.expire();
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar identidad' }));

    expect(await screen.findByText('Tu sesión terminó')).toBeInTheDocument();
    expect(currentPath(router)).toBe('/login?reason=expired&next=%2F%3Fconversation%3Dc-123');
    expect(screen.queryByRole('dialog')).toBeNull();

    await userEvent.click(screen.getByRole('button', { name: /Dos tarjetas activas/ }));
    await userEvent.type(
      await screen.findByRole('textbox', { name: 'Código de verificación' }),
      DEMO_CODE,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Verificar' }));

    expect(await screen.findByText('Tu conversación c-123 sigue abierta.')).toBeInTheDocument();
    expect(currentPath(router)).toBe('/?conversation=c-123');
  });

  it('sends a staff member back to the console after an expired session', async () => {
    const auth = startAuthServer({ session: sessionView({ role: 'agent' }) });
    const { router, services } = renderApp({ path: '/console' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Resumen' })).toBeInTheDocument();
    auth.expire();
    await services.queryClient.refetchQueries();
    await waitFor(() => {
      expect(currentPath(router)).toBe('/login?reason=expired&next=%2Fconsole');
    });
  });
});

describe('step-up from a feature', () => {
  it('asks for a fresh code, confirms it, and shows the stronger verification', async () => {
    startAuthServer({ session: sessionView() });
    renderApp({ path: '/' });
    await userEvent.click(await screen.findByRole('button', { name: 'Confirmar identidad' }));

    const dialog = await screen.findByRole('dialog', { name: 'Confirma que eres tú' });
    expect(dialog).toHaveAccessibleDescription(/necesitamos un código nuevo/);
    await userEvent.type(
      await within(dialog).findByRole('textbox', { name: 'Código de verificación' }),
      DEMO_CODE,
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Verificar' }));

    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull();
    });
    expect(await screen.findByText('Identidad confirmada.')).toBeInTheDocument();
    expect(screen.getAllByText('Verificación reforzada').length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: 'Confirmar identidad' })).toBeNull();
  });

  it('can be cancelled, returning focus to the button that opened it', async () => {
    startAuthServer({ session: sessionView() });
    renderApp({ path: '/' });
    const trigger = await screen.findByRole('button', { name: 'Confirmar identidad' });
    await userEvent.click(trigger);
    const dialog = await screen.findByRole('dialog');
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Cancelar' }));
    await waitFor(() => {
      expect(screen.queryByRole('dialog')).toBeNull();
    });
    expect(screen.queryByText('Identidad confirmada.')).toBeNull();
  });

  it('explains a wrong step-up code inside the dialog', async () => {
    startAuthServer({ session: sessionView() });
    renderApp({ path: '/' });
    await userEvent.click(await screen.findByRole('button', { name: 'Confirmar identidad' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.type(
      await within(dialog).findByRole('textbox', { name: 'Código de verificación' }),
      '000000',
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Verificar' }));
    expect(await within(dialog).findByRole('alert')).toHaveTextContent('Te quedan 4 intentos.');
  });
});

describe('sign-out and guards', () => {
  it('signs out to the sign-in screen with a notice', async () => {
    const auth = startAuthServer({ session: sessionView() });
    const { router } = renderApp({ path: '/' });
    await userEvent.click(await screen.findByRole('button', { name: 'Cerrar sesión' }));
    expect(await screen.findByText('Cerraste sesión.')).toBeInTheDocument();
    expect(currentPath(router)).toBe('/login?reason=signed-out');
    expect(auth.state.session).toBeNull();
  });

  it('sends a customer who opens the console to the customer home', async () => {
    startAuthServer({ session: sessionView() });
    const { router } = renderApp({ path: '/console' });
    expect(
      await screen.findByRole('heading', { level: 1, name: '¿En qué te ayudamos hoy?' }),
    ).toBeInTheDocument();
    expect(currentPath(router)).toBe('/');
  });

  it('sends staff who open the customer area to the console', async () => {
    startAuthServer({ session: sessionView({ role: 'evaluator' }) });
    const { router } = renderApp({ path: '/' });
    expect(await screen.findByRole('heading', { level: 1, name: 'Resumen' })).toBeInTheDocument();
    expect(currentPath(router)).toBe('/console');
  });

  it('offers a retry when the session check fails', async () => {
    server.use(apiGet('/v1/auth/me', () => problem(500, 'internal-error')));
    renderApp({ path: '/' });
    const alert = await screen.findByRole('alert', {}, { timeout: 10_000 });
    expect(alert).toHaveTextContent('Algo falló de nuestro lado.');
    expect(within(alert).getByRole('button', { name: 'Reintentar' })).toBeInTheDocument();
  });

  it('shows a not-found page for an unknown address', async () => {
    startAuthServer();
    renderApp({ path: '/no-existe' });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'No encontramos esta página' }),
    ).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Ir al inicio' })).toHaveAttribute('href', '/');
  });
});
