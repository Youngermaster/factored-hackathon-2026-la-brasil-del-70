import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { currentPath, renderApp } from '@/test/app';
import { apiPost, problem } from '@/test/msw/api';
import { DEMO_CODE, startAuthServer } from '@/test/msw/auth';
import { server } from '@/test/msw/server';

beforeEach(() => {
  vi.stubEnv('VITE_DEMO_MODE', 'true');
});

afterEach(() => {
  vi.unstubAllEnvs();
});

async function signInAs(personaText: RegExp, code = DEMO_CODE) {
  await userEvent.click(await screen.findByRole('button', { name: personaText }));
  const input = await screen.findByRole('textbox', { name: 'Código de verificación' });
  await userEvent.type(input, code);
  await userEvent.click(screen.getByRole('button', { name: 'Verificar' }));
}

describe('sign-in', () => {
  it('sends a signed-out visitor to sign-in, keeping the destination', async () => {
    startAuthServer();
    const { router } = renderApp({ path: '/?conversation=c-42' });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'Ingresa a tu banca' }),
    ).toBeInTheDocument();
    expect(currentPath(router)).toBe('/login?next=%2F%3Fconversation%3Dc-42');
  });

  it('signs a customer in with a persona and the code, and lands on the customer layout', async () => {
    startAuthServer();
    const { router } = renderApp({ path: '/login' });
    expect(screen.getAllByText('Modo demostración').length).toBeGreaterThan(0);
    await signInAs(/Dos tarjetas activas/);
    expect(await screen.findByRole('heading', { level: 1, name: 'Asistente' })).toBeInTheDocument();
    await waitFor(() => {
      expect(currentPath(router)).toBe('/?conversation=conv-default');
    });
    expect(screen.getByRole('button', { name: 'Cerrar sesión' })).toBeInTheDocument();
  });

  it.each([
    [/Consola de agente/, 'Atiendes traspasos estructurados'],
    [/Consola de evaluación/, 'Revisas registros de ejecución'],
  ])('lands staff on the console (%s)', async (persona, body) => {
    startAuthServer();
    const { router } = renderApp({ path: '/login' });
    await signInAs(persona);
    expect(await screen.findByRole('heading', { level: 1, name: 'Resumen' })).toBeInTheDocument();
    expect(screen.getByText(new RegExp(body))).toBeInTheDocument();
    expect(currentPath(router)).toBe('/console');
  });

  it('shows the demo code only when the challenge carries one, with a countdown', async () => {
    startAuthServer();
    renderApp({ path: '/login' });
    await userEvent.click(await screen.findByRole('button', { name: /Cuenta corriente/ }));
    expect(await screen.findByText(DEMO_CODE)).toBeInTheDocument();
    expect(screen.getByText(/^[45]:\d\d$/).closest('span')?.parentElement).toHaveTextContent(
      /^Vence en [45]:\d\d$/,
    );
    expect(screen.getByRole('heading', { name: 'Ingresa tu código' })).toHaveFocus();
  });

  it('signs in with a document number and the last four phone digits', async () => {
    const auth = startAuthServer();
    renderApp({ path: '/login' });
    await userEvent.click(await screen.findByRole('tab', { name: 'Documento' }));
    await userEvent.click(screen.getByRole('button', { name: 'Enviar código' }));
    expect(
      screen.getByRole('textbox', { name: 'Número de documento' }),
    ).toHaveAccessibleDescription(/Revisa el número/);
    await userEvent.type(
      screen.getByRole('textbox', { name: 'Número de documento' }),
      'CC-10203040',
    );
    await userEvent.type(
      screen.getByRole('textbox', { name: 'Últimos 4 dígitos de tu teléfono' }),
      '4821',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Enviar código' }));
    await userEvent.type(
      await screen.findByRole('textbox', { name: 'Código de verificación' }),
      DEMO_CODE,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Verificar' }));
    expect(await screen.findByRole('heading', { level: 1, name: 'Asistente' })).toBeInTheDocument();
    const start = auth.requests.find((request) => request.url.endsWith('/v1/auth/start'));
    expect(await start?.json()).toEqual({
      kind: 'document',
      document_number: 'CC-10203040',
      phone_last4: '4821',
    });
  });

  it('hides the persona picker outside demo mode', async () => {
    vi.stubEnv('VITE_DEMO_MODE', 'false');
    startAuthServer();
    renderApp({ path: '/login' });
    expect(await screen.findByRole('textbox', { name: 'Número de documento' })).toBeInTheDocument();
    expect(screen.queryByRole('tab')).toBeNull();
    expect(screen.queryByText('Modo demostración')).toBeNull();
  });
});

describe('wrong codes and lockout', () => {
  it('explains a wrong code and counts the attempts left', async () => {
    startAuthServer();
    renderApp({ path: '/login' });
    await signInAs(/Dos tarjetas activas/, '000000');
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent(
      'El código no es correcto o los datos no coinciden. Te quedan 4 intentos.',
    );
    expect(screen.getByRole('textbox', { name: 'Código de verificación' })).toHaveAttribute(
      'aria-invalid',
      'true',
    );
  });

  it('asks for the full code before sending it', async () => {
    startAuthServer();
    renderApp({ path: '/login' });
    await signInAs(/Dos tarjetas activas/, '123');
    expect(await screen.findByRole('alert')).toHaveTextContent('El código tiene 6 dígitos.');
  });

  it('says how long a lockout lasts and blocks the code field', async () => {
    startAuthServer();
    server.use(
      apiPost('/v1/auth/verify', () => problem(429, 'identity-locked', { retryAfter: 900 })),
    );
    renderApp({ path: '/login' });
    await signInAs(/Dos tarjetas activas/, '111111');
    expect(await screen.findByRole('alert')).toHaveTextContent('Inténtalo de nuevo en 15 minutos.');
    expect(screen.getByRole('textbox', { name: 'Código de verificación' })).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Verificar' })).toBeDisabled();
  });

  it('offers a new code after the code expires on the server', async () => {
    startAuthServer();
    server.use(apiPost('/v1/auth/verify', () => problem(401, 'code-expired')));
    renderApp({ path: '/login' });
    await signInAs(/Dos tarjetas activas/);
    expect(await screen.findByRole('alert')).toHaveTextContent('El código venció. Pide uno nuevo.');
    await userEvent.click(screen.getByRole('button', { name: 'Pedir otro código' }));
    await waitFor(() => {
      expect(screen.queryByRole('alert')).toBeNull();
    });
  });

  it('shows a plain message and the request id when the start fails', async () => {
    startAuthServer();
    server.use(apiPost('/v1/auth/start', () => problem(503, 'service-unavailable')));
    renderApp({ path: '/login' });
    await userEvent.click(await screen.findByRole('button', { name: /Dos tarjetas activas/ }));
    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('Algo falló de nuestro lado.');
    expect(within(alert).getByText('req-test-0001')).toBeInTheDocument();
  });
});

describe('CSRF', () => {
  it('sends the CSRF header on every unsafe request of a sign-in and sign-out', async () => {
    const auth = startAuthServer();
    renderApp({ path: '/login' });
    await signInAs(/Dos tarjetas activas/);
    await waitFor(() => {
      expect(
        auth.requests.some((request) => new URL(request.url).pathname === '/v1/conversations'),
      ).toBe(true);
    });
    await userEvent.click(await screen.findByRole('button', { name: 'Cerrar sesión' }));
    expect(await screen.findByText('Cerraste sesión.')).toBeInTheDocument();
    const unsafe = auth.requests.filter((request) => request.method !== 'GET');
    expect(unsafe.map((request) => new URL(request.url).pathname)).toEqual([
      '/v1/auth/start',
      '/v1/auth/verify',
      '/v1/conversations',
      '/v1/auth/logout',
    ]);
    expect(unsafe.map((request) => request.headers.get('X-CSRF-Token'))).toEqual([
      'csrf-anonymous-1',
      'csrf-anonymous-1',
      'csrf-session',
      'csrf-session',
    ]);
  });
});

describe('verify request', () => {
  it('sends the interface language with the code', async () => {
    let language: unknown = null;
    startAuthServer();
    server.use(
      apiPost('/v1/auth/verify', async ({ request }) => {
        language = ((await request.json()) as { language?: unknown }).language;
        return problem(401, 'verification-failed');
      }),
    );
    renderApp({ path: '/login', locale: 'pt-BR' });
    await userEvent.click(await screen.findByRole('button', { name: /Dois cartões ativos/ }));
    await userEvent.type(
      await screen.findByRole('textbox', { name: 'Código de verificação' }),
      DEMO_CODE,
    );
    await userEvent.click(screen.getByRole('button', { name: 'Verificar' }));
    await screen.findByRole('alert');
    expect(language).toBe('pt');
  });
});
