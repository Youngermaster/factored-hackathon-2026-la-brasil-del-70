import { screen } from '@testing-library/react';
import { HttpResponse } from 'msw';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { axe } from '@/test/axe';
import { renderApp } from '@/test/app';
import { creditApplicationView, handoffView, startAgentServer } from '@/test/msw/agent';
import { apiGet, sessionView } from '@/test/msw/api';
import { startAuthServer } from '@/test/msw/auth';
import {
  assistantMessage,
  conversationView,
  startConversationServer,
  turnView,
} from '@/test/msw/conversation';
import { server } from '@/test/msw/server';
import { startSupervisionServer } from '@/test/msw/supervision';
import { assessmentRecord, customerTraceRecord, staffTraceRecord } from '@/test/msw/trace';

// Whole pages: landmarks and headings are checked too.
const pageRules = { rules: { region: { enabled: true } } };

const richTurn = turnView({
  customer_text: '¿Soy elegible para un préstamo?',
  message: assistantMessage({
    text: 'Resultado indicativo.',
    balances: [
      {
        product_ref: 'products:prd-fixture-1',
        product_type: 'checking_account',
        masked_number: { last4: '6930' },
        current_balance: { amount: '3537.55', currency: 'MXN' },
        available_credit: null,
        credit_limit: null,
        over_limit: false,
        as_of: '2026-06-18T05:59:59Z',
      },
    ],
    eligibility: {
      outcome: 'review_required',
      reasons: [{ reason_code: 'borderline_risk_interval', clause: 'ELG-ALL-2@1' }],
      missing_facts: [],
      uncertainty: 'borderline_estimate',
      review_path: 'request_human_contact',
      disclaimer: 'indicative_not_an_offer_or_decision',
      synthetic: true,
    },
    escalation: { handoff_id: 'ho-fixture-7', expected_response_by: '2026-09-30T15:00:00Z' },
    citations: [{ clause: 'ELG-ALL-2@1', excerpt: 'Texto de la cláusula.' }],
  }),
});

beforeEach(() => {
  vi.stubEnv('VITE_DEMO_MODE', 'true');
});

afterEach(() => {
  vi.unstubAllEnvs();
});

async function expectAccessible() {
  expect(await axe(document.body, pageRules)).toHaveNoViolations();
}

describe.each(['light', 'dark'] as const)('product surfaces in the %s theme', (theme) => {
  it('the chat with message parts and the glass box', async () => {
    startAuthServer({ session: sessionView() });
    startConversationServer({
      histories: {
        'conv-a': {
          conversation: conversationView({ conversation_id: 'conv-a' }),
          turns: [richTurn],
        },
      },
      traces: {
        'conv-a': {
          conversation_id: 'conv-a',
          records: [customerTraceRecord({ eligibility_assessments: [assessmentRecord()] })],
        },
      },
    });
    renderApp({ path: '/?conversation=conv-a', theme });
    await screen.findByRole('region', { name: 'Orientación de elegibilidad' });
    await screen.findByRole('article', { name: /Turno 1/ });
    await expectAccessible();
  });

  it('the glass box on its own route', async () => {
    startAuthServer({ session: sessionView() });
    startConversationServer({
      histories: {
        'conv-a': {
          conversation: conversationView({ conversation_id: 'conv-a' }),
          turns: [richTurn],
        },
      },
      traces: { 'conv-a': { conversation_id: 'conv-a', records: [customerTraceRecord()] } },
    });
    renderApp({ path: '/glass-box/conv-a', theme });
    await screen.findByRole('article', { name: /Turno 1/ });
    await expectAccessible();
  });

  it('the agent inbox, a handoff, and the credit applications', async () => {
    startAuthServer({ session: sessionView({ role: 'agent' }) });
    startAgentServer({
      handoffs: [
        handoffView({
          card_request: { action: 'unblock_request', product_ref: 'products:prd-fixture-2' },
        }),
      ],
      applications: [creditApplicationView()],
    });
    const { router } = renderApp({ path: '/console/inbox', theme });
    await screen.findByRole('table');
    await expectAccessible();
    await router.navigate('/console/inbox/ho-fixture-1');
    await screen.findByRole('region', { name: 'Solicitud de tarjeta' });
    await expectAccessible();
    await router.navigate('/console/credit-applications');
    await screen.findByRole('link', { name: 'app-fixture-1' });
    await expectAccessible();
    await router.navigate('/console/credit-applications/app-fixture-1');
    await screen.findByRole('heading', { level: 1, name: 'app-fixture-1' });
    await expectAccessible();
  });

  it('the evaluation view, empty, and the evaluator trace', async () => {
    startAuthServer({ session: sessionView({ role: 'evaluator' }) });
    server.use(
      apiGet('/v1/eval/summaries', () => HttpResponse.json({ summaries: [] })),
      apiGet('/v1/eval/conversations/:id/trace', () =>
        HttpResponse.json({ conversation_id: 'conv-a', records: [staffTraceRecord()] }),
      ),
    );
    const { router } = renderApp({ path: '/console/dashboard', theme });
    await screen.findByText('Todavía no hay datos para el dashboard');
    await expectAccessible();
    await router.navigate('/console/evaluation');
    await screen.findByText('Todavía no hay resultados publicados');
    await expectAccessible();
    await router.navigate('/console/traces/conv-a');
    await screen.findByRole('region', { name: 'Solo evaluación' });
    await expectAccessible();
  });

  it('the supervision view', async () => {
    startAuthServer({ session: sessionView({ role: 'evaluator' }) });
    startSupervisionServer();
    renderApp({ path: '/console/supervision', theme });
    await screen.findByRole('table', { name: 'Componentes y modelo servido' });
    await screen.findByText('L0: normal');
    await expectAccessible();
  });

  it('the demo guide and the About page', async () => {
    startAuthServer();
    const { router } = renderApp({ path: '/demo', theme });
    await screen.findByRole('heading', { level: 1, name: 'Guía de demostración' });
    await expectAccessible();
    await router.navigate('/about');
    await screen.findByRole('heading', { level: 1, name: 'Qué hace este asistente' });
    await expectAccessible();
  });
});
