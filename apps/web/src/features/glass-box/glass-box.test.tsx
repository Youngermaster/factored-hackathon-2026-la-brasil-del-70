import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import type { Schema } from '@/shared/api';
import { renderApp } from '@/test/app';
import { apiGet, sessionView } from '@/test/msw/api';
import { startAuthServer } from '@/test/msw/auth';
import {
  assistantMessage,
  conversationView,
  startConversationServer,
  turnView,
} from '@/test/msw/conversation';
import { server } from '@/test/msw/server';
import {
  assessmentRecord,
  customerTraceRecord,
  decision,
  ruleResult,
  staffTraceRecord,
} from '@/test/msw/trace';

async function openTrace(records: Schema<'CustomerTraceRecord'>[], turns = [turnView()]) {
  startAuthServer({ session: sessionView() });
  startConversationServer({
    histories: {
      'conv-g': { conversation: conversationView({ conversation_id: 'conv-g' }), turns },
    },
    traces: { 'conv-g': { conversation_id: 'conv-g', records } },
  });
  renderApp({ path: '/?conversation=conv-g' });
  const panel = await screen.findByRole('region', { name: 'Registro de ejecución' });
  await within(panel).findByRole('article', { name: /Turno 1/ });
  return panel;
}

describe('the glass box', () => {
  it('shows rules, cited clauses, tools with verification, and the reasoning note', async () => {
    const panel = await openTrace(
      [
        customerTraceRecord({
          tool_calls: [
            {
              sequence: 1,
              tool: 'block_card',
              arguments: { product_id: 'prd-fixture-2', reason: 'lost' },
              idempotency_key: 'idem-fixture',
              status: 'ok',
              error_code: null,
              attempts: 1,
              latency_ms: 12,
              result_summary: 'blocked',
              verification: {
                check: 'product_status_is_blocked',
                checked_at: '2026-09-29T15:00:01Z',
                evidence: 'products:prd-fixture-2',
                mismatch_code: null,
                verified: true,
              },
            },
          ],
        }),
      ],
      [
        turnView({
          message: assistantMessage({
            citations: [
              { clause: 'ACC-ALL-1@1', excerpt: 'Siempre te indicamos la fecha del corte.' },
            ],
          }),
        }),
      ],
    );
    expect(
      within(panel).getByText(/El razonamiento del modelo no se muestra, por diseño/),
    ).toBeInTheDocument();
    const turn = within(panel).getByRole('article', { name: /Turno 1/ });
    expect(within(turn).getByText('START -> BALANCES')).toBeInTheDocument();
    expect(within(turn).getByText('balance_inquiry')).toBeInTheDocument();
    expect(within(turn).getByText('ACC.as_of_disclosed@1')).toBeInTheDocument();
    expect(within(turn).getByText('Siempre te indicamos la fecha del corte.')).toBeInTheDocument();
    expect(within(turn).getByText('ESC-ALL-1@1')).toBeInTheDocument();
    expect(within(turn).getByText('block_card')).toBeInTheDocument();
    expect(within(turn).getByText('Comprobado')).toBeInTheDocument();
    expect(
      within(turn).getByText(/products:prd-fixture-2/, { selector: 'span' }),
    ).toBeInTheDocument();
    expect(within(turn).getByText('product_id=prd-fixture-2, reason=lost')).toBeInTheDocument();
  });

  it('links a message and its trace entry in both directions', async () => {
    const panel = await openTrace([customerTraceRecord({ turn_id: 'turn-fixture-1' })]);
    const message = screen.getByRole('article', { name: 'Asistente' });
    const entry = within(panel).getByRole('article', { name: /Turno 1/ });

    await userEvent.click(within(message).getByRole('button', { name: 'Ver en el registro' }));
    expect(entry).toHaveAttribute('data-selected', 'true');
    expect(message).toHaveAttribute('data-selected', 'true');

    await userEvent.click(within(message).getByRole('button', { name: 'Ver en el registro' }));
    expect(entry).not.toHaveAttribute('data-selected');

    await userEvent.click(within(entry).getByRole('button', { name: 'Ver el mensaje en el chat' }));
    expect(message).toHaveAttribute('data-selected', 'true');
    expect(within(message).getByRole('button', { name: 'Ver en el registro' })).toHaveAttribute(
      'aria-pressed',
      'true',
    );
  });

  it('keeps the risk estimate and the eligibility decision apart, and hides estimate values', async () => {
    const panel = await openTrace([
      customerTraceRecord({
        workflow: { id: 'credit', version: 1 },
        eligibility_assessments: [assessmentRecord()],
        risk_estimates_used: [
          {
            estimate_id: 'est-fixture-1',
            model: 'risk_estimator:score_band@1',
            label_definition: 'dpd90_snapshot',
          },
        ],
        decisions: [
          decision({
            state: 'ASSESS_ELIGIBILITY',
            rule_results: [
              ruleResult({
                rule_id: 'ELG.credit_score_minimum',
                passed: true,
                reason_code: 'credit_score_meets_minimum',
                clause_refs: ['ELG-MX-1@1'],
              }),
            ],
          }),
        ],
      }),
    ]);
    const risk = within(panel).getByRole('region', { name: 'Estimación de riesgo' });
    const eligibility = within(panel).getByRole('region', { name: 'Decisión de elegibilidad' });
    expect(risk).not.toContainElement(eligibility);
    expect(eligibility).not.toContainElement(risk);
    expect(within(risk).getByText('risk_estimator:score_band@1')).toBeInTheDocument();
    expect(
      within(risk).getByText('Estimación con datos sintéticos, no una decisión de crédito.'),
    ).toBeInTheDocument();
    expect(
      within(risk).getByText('Los valores de la estimación no se muestran al cliente.'),
    ).toBeInTheDocument();
    expect(risk.textContent).not.toMatch(/Probabilidad|Intervalo|Banda/);
    expect(within(eligibility).getByText('ELG.credit_score_minimum@1')).toBeInTheDocument();
    expect(within(eligibility).getByText('cumple')).toBeInTheDocument();
    expect(within(eligibility).getByText('ELG-MX-1@1')).toBeInTheDocument();
    expect(
      within(panel).getByText(/El modelo de lenguaje no recibió ninguno de los dos/),
    ).toBeInTheDocument();
  });

  it('marks a workflow switch and labels a pre-check without calling it a failure', async () => {
    const panel = await openTrace([
      customerTraceRecord({
        workflow: { id: 'dispute', version: 1 },
        workflow_before: { id: 'card_support', version: 1 },
        decisions: [
          decision({
            state: 'ANSWER_BALANCE',
            kind: 'abstain',
            rule_results: [
              ruleResult({ rule_id: 'AUTH.session_valid', reason_code: 'session_valid' }),
              ruleResult({
                passed: false,
                effect: 'abstain',
                reason_code: 'as_of_missing',
                missing_facts: ['answer_as_of'],
              }),
            ],
            decisive_rule_ids: ['ACC.as_of_disclosed'],
          }),
        ],
      }),
    ]);
    expect(within(panel).getByText('Cambió desde Tarjetas')).toBeInTheDocument();
    expect(within(panel).getByText('comprobación previa', { exact: false })).toBeInTheDocument();
    expect(within(panel).getByText('1 cumplen, 0 no cumplen, 1 sin datos.')).toBeInTheDocument();
    expect(within(panel).getByText('sin datos')).toBeInTheDocument();
  });

  it('explains an empty record before the first answer', async () => {
    startAuthServer({ session: sessionView() });
    startConversationServer();
    renderApp({ path: '/' });
    // The panel can re-render once the chat's other queries settle, so look it up fresh on every retry.
    await waitFor(() => {
      const panel = screen.getByRole('region', { name: 'Registro de ejecución' });
      expect(within(panel).getByText('Todavía no hay turnos')).toBeInTheDocument();
    });
  });
});

describe('the evaluator glass box', () => {
  it('looks a conversation up and adds what customers never see, in its own section', async () => {
    startAuthServer({ session: sessionView({ role: 'evaluator' }) });
    server.use(
      apiGet('/v1/eval/conversations/:id/trace', ({ params }) =>
        HttpResponse.json({
          conversation_id: String(params['id']),
          records: [
            staffTraceRecord({
              workflow: { id: 'credit', version: 1 },
              risk_tier: 'elevated',
              trust_events_added: ['injection_detected'],
              safety_interventions: ['injection_detected'],
              eligibility_assessments: [assessmentRecord()],
              risk_estimates: [
                {
                  estimate_id: 'est-fixture-1',
                  model: 'risk_estimator:score_band@1',
                  band: 'medium',
                  probability: '0.143',
                  interval_low: '0.08',
                  interval_high: '0.21',
                  flags: ['wide_interval'],
                  label_definition: 'dpd90_snapshot',
                  latency_ms: 2,
                },
              ],
            }),
          ],
        }),
      ),
    );
    renderApp({ path: '/console/traces' });
    await userEvent.type(
      await screen.findByRole('textbox', { name: 'Referencia de la conversación' }),
      'conv-eval-1',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Buscar' }));
    const internal = await screen.findByRole('region', { name: 'Solo evaluación' });
    expect(within(internal).getByText('elevado')).toBeInTheDocument();
    expect(within(internal).getAllByText('injection_detected')).toHaveLength(2);
    const risk = screen.getByRole('region', { name: 'Estimación de riesgo' });
    expect(within(risk).getByText('14.3 %')).toBeInTheDocument();
    expect(within(risk).getByText('8 % a 21 %')).toBeInTheDocument();
    expect(within(risk).getByText('intervalo amplio')).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Decisión de elegibilidad' })).not.toContainElement(
      risk,
    );
  });

  it('asks for a reference before showing anything', async () => {
    startAuthServer({ session: sessionView({ role: 'evaluator' }) });
    renderApp({ path: '/console/traces' });
    expect(await screen.findByText('Busca una conversación')).toBeInTheDocument();
  });
});
