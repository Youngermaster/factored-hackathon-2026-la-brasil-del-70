import { HttpResponse } from 'msw';

import type { Schema } from '@/shared/api';

import { apiGet, apiPost, problem } from './api';
import { server } from './server';

/** Agent console fixtures and a stateful fake of `/v1/agent`, typed from the generated schema. Synthetic. */
type Handoff = Schema<'HandoffView'>;
type Application = Schema<'CreditApplicationView'>;

const inHours = (hours: number) => new Date(Date.now() + hours * 3_600_000).toISOString();

export function handoffView(overrides: Partial<Handoff> = {}): Handoff {
  return {
    handoff_id: 'ho-fixture-1',
    schema_version: '1.3.0',
    status: 'open',
    priority: 'medium',
    workflow: { id: 'account_inquiry', version: 1 },
    request: { intent: 'balance_inquiry', summary: 'El cliente impugna el saldo de su cuenta.' },
    escalation_reason: { code: 'human_requested', detail: 'customer asked for a person' },
    state_at_escalation: 'BALANCES',
    verified_facts: [
      { fact: 'Saldo de la cuenta **** 6930: 3,537.55 MXN', source: 'products:prd-fixture-1' },
    ],
    actions_taken: [],
    policy_basis: ['ESC-ALL-1@1'],
    policy_excerpts: [
      {
        clause: 'ESC-ALL-1@1',
        excerpt: 'Una persona del equipo toma la conversación cuando lo pides.',
      },
    ],
    open_questions: ['Qué movimiento cree el cliente que falta.'],
    customer_sentiment: 'negative',
    language: 'es',
    jurisdiction: 'MX',
    auth: { level: 'otp_verified', expires_at: inHours(1) },
    conversation_ref: 'conv-fixture-1',
    customer_ref: 'customers:cli-fixture-1',
    case_ref: null,
    card_request: null,
    credit_review: null,
    claimed_by: null,
    claimed_at: null,
    resolution: null,
    created_at: '2026-09-29T14:00:00Z',
    sla_due: inHours(3),
    ...overrides,
  };
}

export function creditApplicationView(overrides: Partial<Application> = {}): Application {
  return {
    application_id: 'app-fixture-1',
    customer_id: 'cli-fixture-2',
    product_code: 'CO-PL-STANDARD',
    requested_amount: { amount: '5000000.00', currency: 'COP' },
    requested_term_months: 24,
    purpose: 'general_purpose',
    declared_monthly_income: null,
    assessment_ref: 'eligibility_assessments:asm-fixture-1',
    origin_conversation_id: 'conv-fixture-2',
    status: 'submitted',
    status_history: [],
    synthetic_policy: true,
    created_at: '2026-09-28T10:00:00Z',
    updated_at: '2026-09-28T10:00:00Z',
    ...overrides,
  };
}

const matches = (values: string[], value: string | undefined) =>
  values.length === 0 || (value !== undefined && values.includes(value));

/** A stateful fake: filters like the API, claims open handoffs, resolves claimed ones, and records requests. */
export function startAgentServer(
  initial: { handoffs?: Handoff[]; applications?: Application[] } = {},
) {
  const handoffs = new Map(
    (initial.handoffs ?? [handoffView()]).map((item) => [item.handoff_id, item]),
  );
  const applications = initial.applications ?? [creditApplicationView()];
  const listed: URL[] = [];

  server.use(
    apiGet('/v1/agent/handoffs', ({ request }) => {
      const url = new URL(request.url);
      listed.push(url);
      const all = (name: string) => url.searchParams.getAll(name);
      const before = url.searchParams.get('sla_due_before');
      const result = [...handoffs.values()].filter(
        (item) =>
          matches(all('workflow'), item.workflow?.id) &&
          matches(all('priority'), item.priority) &&
          matches(all('reason'), item.escalation_reason.code) &&
          matches(all('language'), item.language) &&
          matches(all('status'), item.status) &&
          (before === null || item.sla_due <= before),
      );
      return HttpResponse.json({ handoffs: result });
    }),
    apiGet('/v1/agent/handoffs/:id', ({ params }) => {
      const item = handoffs.get(String(params['id']));
      return item === undefined ? problem(404, 'resource-not-found') : HttpResponse.json(item);
    }),
    apiPost('/v1/agent/handoffs/:id/claim', ({ params }) => {
      const item = handoffs.get(String(params['id']));
      if (item === undefined) {
        return problem(404, 'resource-not-found');
      }
      if (item.status !== 'open') {
        return problem(409, 'invalid-state-transition');
      }
      const claimed: Handoff = {
        ...item,
        status: 'claimed',
        claimed_by: 'agent-demo-01',
        claimed_at: new Date().toISOString(),
      };
      handoffs.set(item.handoff_id, claimed);
      return HttpResponse.json(claimed);
    }),
    apiPost('/v1/agent/handoffs/:id/resolve', async ({ params, request }) => {
      const item = handoffs.get(String(params['id']));
      const body = (await request.json()) as Schema<'ResolveHandoffRequest'>;
      if (item?.status !== 'claimed') {
        return problem(409, 'invalid-state-transition');
      }
      const resolved: Handoff = {
        ...item,
        status: 'resolved',
        resolution: {
          outcome: body.outcome,
          note: body.note,
          resolved_by: 'agent-demo-01',
          resolved_at: new Date().toISOString(),
        },
      };
      handoffs.set(item.handoff_id, resolved);
      return HttpResponse.json(resolved);
    }),
    apiGet('/v1/agent/credit-applications', () => HttpResponse.json({ applications })),
    apiGet('/v1/agent/credit-applications/:id', ({ params }) => {
      const item = applications.find(
        (application) => application.application_id === String(params['id']),
      );
      return item === undefined ? problem(404, 'resource-not-found') : HttpResponse.json(item);
    }),
  );

  return { handoffs, listed };
}
