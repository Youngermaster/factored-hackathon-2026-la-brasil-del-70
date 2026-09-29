import { http, HttpResponse } from 'msw';

import type { components } from '../../shared/api/generated/schema';

/**
 * Fixtures and handlers for the Tuesday MVP contract (docs/plans/mvp-tuesday.md, step 0), typed from the
 * generated API types so they break when the backend contract changes. They are test data only: the
 * customer, amounts, and ids are synthetic. Features opt in with `server.use(...mvpHandlers)`.
 */
type Schemas = components['schemas'];

const CONVERSATION_ID = 'conv-demo-0001';
const AT = '2026-06-17T15:00:00Z';

export const profileFixture: Schemas['ProfileView'] = {
  customer_first_name: 'Ana',
  assistant: {
    name: 'Luna',
    avatar_id: 'avatar-01',
    avatar_url: '/avatars/avatar-01.png',
    updated_at: null,
  },
};

export const conversationFixture: Schemas['ConversationView'] = {
  conversation_id: CONVERSATION_ID,
  status: 'active',
  language: null,
  workflow: { id: 'router', version: 1 },
  state: 'START',
  created_at: AT,
  updated_at: AT,
};

function message(overrides: Partial<Schemas['AssistantMessage']>): Schemas['AssistantMessage'] {
  return {
    language: 'es',
    text: '',
    action_statuses: [],
    balances: [],
    card_status: [],
    citations: [],
    credit_products: [],
    notices: [],
    payment_statuses: [],
    step_up_required: false,
    ...overrides,
  };
}

function turn(
  turnId: string,
  overrides: Partial<Schemas['TurnResponse']>,
): Schemas['TurnResponse'] {
  return {
    turn_id: turnId,
    conversation_id: CONVERSATION_ID,
    correlation_id: 'req-0000000000000001',
    workflow: { id: 'account_inquiry', version: 1 },
    state: 'BALANCES',
    outcome: 'resolved',
    replayed: false,
    message: message({}),
    ...overrides,
  };
}

/** An account answer: one balance, with the data's as-of instant. */
export const accountTurnFixture = turn('9b2f0d1e-0000-4000-8000-000000000001', {
  message: message({
    text: 'Tu cuenta de ahorro terminada en 4821 tiene 12.500,00 MXN (datos al 17/06/2026).',
    balances: [
      {
        product_ref: 'products:PRD-DEMO0001',
        product_type: 'savings_account',
        masked_number: { last4: '4821' },
        current_balance: { amount: '12500.00', currency: 'MXN' },
        credit_limit: null,
        available_credit: null,
        over_limit: false,
        as_of: AT,
      },
    ],
  }),
});

/** A card, dispute, or credit request in demo mode: a handoff and the labeled simulated agent. */
export const escalationTurnFixture = turn('9b2f0d1e-0000-4000-8000-000000000002', {
  correlation_id: 'req-0000000000000002',
  workflow: { id: 'card_support', version: 1 },
  state: 'ESCALATED',
  outcome: 'escalated',
  message: message({
    text: 'Paso tu solicitud a un agente de servicio.',
    escalation: { handoff_id: 'ho-demo-0001', expected_response_by: '2026-06-18T15:00:00Z' },
    simulated_agent: {
      agent_display_name: 'Agente simulado',
      text: 'Esta es una respuesta simulada de demostración; ninguna persona revisó tu caso.',
      joined_at: AT,
      simulated: true,
    },
  }),
});

/** A rename: the reply carries the new assistant profile so the header updates without a reload. */
export const renameTurnFixture = turn('9b2f0d1e-0000-4000-8000-000000000003', {
  correlation_id: 'req-0000000000000003',
  workflow: { id: 'router', version: 1 },
  state: 'START',
  message: message({ text: 'Listo, ahora me llamo Sol.' }),
  assistant_profile: { ...profileFixture.assistant, name: 'Sol', updated_at: AT },
});

export const mvpHandlers = [
  http.get('*/v1/profile', () => HttpResponse.json(profileFixture)),
  http.post('*/v1/conversations', () => HttpResponse.json(conversationFixture, { status: 201 })),
  http.post('*/v1/conversations/:conversationId/turns', () =>
    HttpResponse.json(accountTurnFixture),
  ),
];
