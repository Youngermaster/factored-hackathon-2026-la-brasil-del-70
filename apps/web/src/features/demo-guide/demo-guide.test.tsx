import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { PERSONAS } from '@/features/auth';
import { renderApp } from '@/test/app';
import { startAuthServer } from '@/test/msw/auth';

import { SCENARIOS } from './model/scenarios';

afterEach(() => {
  vi.unstubAllEnvs();
});

describe('the demo guide', () => {
  it('covers every workflow with normal, ambiguous or unsupported, and escalation paths in es and pt', () => {
    for (const workflow of ['account_inquiry', 'card_support', 'dispute', 'credit'] as const) {
      const paths = new Set(
        SCENARIOS.filter((item) => item.workflow === workflow).map((item) => item.path),
      );
      expect([...paths].sort(), workflow).toEqual(['ambiguous', 'escalation', 'normal']);
    }
    const personas = new Set(PERSONAS.map((persona) => persona.id));
    for (const scenario of SCENARIOS) {
      expect(personas.has(scenario.persona), scenario.id).toBe(true);
      expect(scenario.es.length, scenario.id).toBeGreaterThan(0);
      expect(scenario.pt.length, scenario.id).toBeGreaterThan(0);
    }
  });

  it('is linked from sign-in in demo mode and copies an example message', async () => {
    vi.stubEnv('VITE_DEMO_MODE', 'true');
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
    startAuthServer();
    renderApp({ path: '/login' });
    await userEvent.click(
      await screen.findByRole('link', { name: 'Guía de demostración para jurados' }),
    );
    await screen.findByRole('heading', { level: 1, name: 'Guía de demostración' });
    const balances = screen.getByRole('region', { name: 'Saldos' });
    expect(within(balances).getByText('acc-mx-accounts')).toBeInTheDocument();
    await userEvent.click(
      within(balances).getByRole('button', { name: /Copiar: ¿Cuál es el saldo de mis cuentas\?/ }),
    );
    expect(writeText).toHaveBeenCalledWith('¿Cuál es el saldo de mis cuentas?');
    expect(await within(balances).findByText('Copiado')).toBeInTheDocument();
    expect(within(balances).getByText('Qual é o saldo das minhas contas?')).toBeInTheDocument();
  });

  it('does not exist outside demo mode', async () => {
    vi.stubEnv('VITE_DEMO_MODE', 'false');
    startAuthServer();
    renderApp({ path: '/demo' });
    expect(
      await screen.findByRole('heading', { level: 1, name: 'No encontramos esta página' }),
    ).toBeInTheDocument();
  });
});

describe('the About page', () => {
  it.each([
    ['es-MX', 'Qué hace este asistente', /nunca una oferta ni una decisión/],
    ['pt-BR', 'O que este assistente faz', /nunca uma oferta nem uma decisão/],
    ['en-US', 'What this assistant does', /never an offer or a decision/],
  ] as const)(
    'explains the four workflows and the synthetic credit indication in %s',
    async (locale, title, credit) => {
      startAuthServer();
      renderApp({ path: '/about', locale });
      await screen.findByRole('heading', { level: 1, name: title });
      // Four workflow cards and four notes (credit, data, transparency, a person).
      expect(screen.getAllByRole('heading', { level: 2 })).toHaveLength(8);
      expect(screen.getByText(credit)).toBeInTheDocument();
    },
  );
});
