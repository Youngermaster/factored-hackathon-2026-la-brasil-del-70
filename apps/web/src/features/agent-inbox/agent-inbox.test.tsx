import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import { currentPath, renderApp } from '@/test/app';
import { creditApplicationView, handoffView, startAgentServer } from '@/test/msw/agent';
import { sessionView } from '@/test/msw/api';
import { startAuthServer } from '@/test/msw/auth';

const inHours = (hours: number) => new Date(Date.now() + hours * 3_600_000).toISOString();

const HANDOFFS = [
  handoffView({
    handoff_id: 'ho-a',
    priority: 'low',
    request: { intent: 'balance_inquiry', summary: 'Saldo impugnado' },
    sla_due: inHours(20),
  }),
  handoffView({
    handoff_id: 'ho-b',
    priority: 'critical',
    workflow: { id: 'card_support', version: 1 },
    request: { intent: 'card_unblock_request', summary: 'Desbloqueo de tarjeta' },
    escalation_reason: { code: 'card_unblock_requested', detail: 'unblock requested' },
    language: 'pt',
    sla_due: inHours(-1),
  }),
  handoffView({
    handoff_id: 'ho-c',
    priority: 'high',
    workflow: { id: 'credit', version: 1 },
    request: { intent: 'credit_eligibility', summary: 'Revisión de elegibilidad' },
    escalation_reason: {
      code: 'credit_review_required',
      detail: 'credit_review_required: review_required',
    },
    status: 'claimed',
    claimed_by: 'agent-demo-01',
    sla_due: inHours(2),
  }),
];

function openInbox(path = '/console/inbox') {
  startAuthServer({ session: sessionView({ role: 'agent' }) });
  const agent = startAgentServer({ handoffs: HANDOFFS });
  const view = renderApp({ path });
  return { agent, ...view };
}

const rowNames = () =>
  screen
    .getAllByRole('link')
    .filter((link) => link.getAttribute('href')?.startsWith('/console/inbox/'))
    .map((link) => link.textContent);

describe('the agent inbox', () => {
  it('lists handoffs by SLA, states the SLA in words, and sorts by priority', async () => {
    openInbox();
    await screen.findByRole('table', { name: '3 traspasos' });
    expect(rowNames()).toEqual([
      'Desbloqueo de tarjeta',
      'Elegibilidad de crédito',
      'Consulta de saldo',
    ]);
    expect(screen.getByText(/Vencido, hace 1 hora/)).toBeInTheDocument();
    expect(screen.getByText(/Vence dentro de 2 horas/)).toBeInTheDocument();

    await userEvent.click(screen.getByRole('button', { name: /Prioridad/ }));
    expect(rowNames()).toEqual([
      'Desbloqueo de tarjeta',
      'Elegibilidad de crédito',
      'Consulta de saldo',
    ]);
    await userEvent.click(screen.getByRole('button', { name: /Prioridad/ }));
    expect(rowNames()).toEqual([
      'Consulta de saldo',
      'Elegibilidad de crédito',
      'Desbloqueo de tarjeta',
    ]);
  });

  it.each([
    ['Flujo', 'Tarjetas', 'workflow=card_support', ['Desbloqueo de tarjeta']],
    ['Prioridad', 'Alta', 'priority=high', ['Elegibilidad de crédito']],
    ['Motivo', 'Revisión de crédito', 'reason=credit_review_required', ['Elegibilidad de crédito']],
    ['Idioma', 'Portugués', 'language=pt', ['Desbloqueo de tarjeta']],
    ['Estado', 'Tomado', 'status=claimed', ['Elegibilidad de crédito']],
    ['Vencimiento', 'Vencidos', 'due=overdue', ['Desbloqueo de tarjeta']],
  ])('filters by %s through the URL and the API', async (label, option, param, expected) => {
    const { agent, router } = openInbox();
    await screen.findByRole('table');
    await userEvent.selectOptions(screen.getByRole('combobox', { name: label }), option);
    await waitFor(() => {
      expect(rowNames()).toEqual(expected);
    });
    expect(currentPath(router)).toContain(param);
    const last = agent.listed.at(-1);
    expect(last?.search).toMatch(param.startsWith('due') ? /sla_due_before=/ : new RegExp(param));
  });

  it('explains an empty result under filters', async () => {
    openInbox('/console/inbox?workflow=dispute');
    expect(await screen.findByText('Ningún traspaso coincide con los filtros')).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Quitar filtros' }));
    await screen.findByRole('table', { name: '3 traspasos' });
  });
});

describe('a handoff', () => {
  it('renders every section, credit review and card request included, never a transcript', async () => {
    startAuthServer({ session: sessionView({ role: 'agent' }) });
    startAgentServer({
      handoffs: [
        handoffView({
          handoff_id: 'ho-full',
          actions_taken: [
            {
              action: 'block_card',
              target: 'products:prd-fixture-2',
              status: 'executed',
              confirmed: true,
              verification: 'verified',
              evidence: 'products:prd-fixture-2',
            },
          ],
          card_request: { action: 'replacement_request', product_ref: 'products:prd-fixture-2' },
          credit_review: {
            product_code: 'MX-PL-STANDARD',
            eligibility_outcome: 'review_required',
            reason_codes: ['borderline_risk_interval'],
            rule_ids: ['ELG.risk_interval_clear'],
            review_reasons: ['borderline_risk_interval'],
            missing_facts: [],
            application_ref: null,
            risk: {
              band: 'medium',
              interval_low: '0.08',
              interval_high: '0.21',
              label_definition: 'dpd90_snapshot',
              model: 'risk_estimator:score_band@1',
            },
          },
        }),
      ],
    });
    renderApp({ path: '/console/inbox/ho-full' });
    await screen.findByRole('heading', {
      level: 1,
      name: 'Consulta de saldo',
    });
    const facts = screen.getByRole('region', { name: 'Hechos verificados' });
    expect(within(facts).getByText('products:prd-fixture-1')).toBeInTheDocument();
    const actions = screen.getByRole('region', { name: 'Acciones realizadas' });
    expect(within(actions).getByText('Verificado')).toBeInTheDocument();
    const policy = screen.getByRole('region', { name: 'Base de política' });
    expect(
      within(policy).getByText('Una persona del equipo toma la conversación cuando lo pides.'),
    ).toBeInTheDocument();
    expect(screen.getByRole('region', { name: 'Preguntas abiertas' })).toHaveTextContent(
      'Qué movimiento',
    );
    const credit = screen.getByRole('region', { name: 'Revisión de crédito' });
    expect(within(credit).getByText('Requiere revisión de una persona')).toBeInTheDocument();
    expect(within(credit).getByText('8 % a 21 %')).toBeInTheDocument();
    expect(
      within(credit).getByText('Estimación con datos sintéticos, no una decisión de crédito.'),
    ).toBeInTheDocument();
    const card = screen.getByRole('region', { name: 'Solicitud de tarjeta' });
    expect(within(card).getByText('Solicitud de reposición')).toBeInTheDocument();
    expect(screen.getByText('Negativo')).toBeInTheDocument();
  });

  it('is claimed and then resolved, each behind a confirmation, and the inbox refreshes', async () => {
    const { agent } = openInbox('/console/inbox/ho-a');
    await userEvent.click(await screen.findByRole('button', { name: 'Tomar traspaso' }));
    const claim = await screen.findByRole('dialog', { name: 'Tomar este traspaso' });
    await userEvent.click(within(claim).getByRole('button', { name: 'Tomar' }));
    expect(
      await screen.findByText('Tomaste el traspaso. Quedó registrado en la auditoría.'),
    ).toBeInTheDocument();
    expect(agent.handoffs.get('ho-a')?.status).toBe('claimed');

    await userEvent.click(await screen.findByRole('button', { name: 'Resolver' }));
    const resolve = await screen.findByRole('dialog', { name: 'Resolver este traspaso' });
    await userEvent.selectOptions(
      within(resolve).getByRole('combobox', { name: 'Resultado' }),
      'Caso actualizado',
    );
    await userEvent.type(
      within(resolve).getByRole('textbox', { name: 'Nota' }),
      'Revisado con el cliente.',
    );
    await userEvent.click(within(resolve).getByRole('button', { name: 'Resolver' }));
    expect(
      await screen.findByText('Traspaso resuelto. Quedó registrado en la auditoría.'),
    ).toBeInTheDocument();
    expect(agent.handoffs.get('ho-a')?.resolution?.outcome).toBe('case_updated');
    expect(await screen.findByText('Revisado con el cliente.')).toBeInTheDocument();

    await userEvent.click(screen.getByRole('link', { name: 'Volver a la bandeja' }));
    const table = await screen.findByRole('table');
    const row = within(table).getByRole('link', { name: 'Consulta de saldo' }).closest('tr');
    expect(row).toHaveTextContent('Resuelto');
  });

  it('says so when someone else changed the handoff first', async () => {
    const { agent } = openInbox('/console/inbox/ho-a');
    await userEvent.click(await screen.findByRole('button', { name: 'Tomar traspaso' }));
    const current = agent.handoffs.get('ho-a');
    if (current !== undefined) {
      agent.handoffs.set('ho-a', { ...current, status: 'claimed' });
    }
    const claim = await screen.findByRole('dialog');
    await userEvent.click(within(claim).getByRole('button', { name: 'Tomar' }));
    expect(await within(claim).findByRole('alert')).toHaveTextContent(
      'Otra persona cambió este traspaso',
    );
  });
});

describe('credit applications', () => {
  it('lists review items read only and opens one with its links', async () => {
    startAuthServer({ session: sessionView({ role: 'agent' }) });
    startAgentServer({ applications: [creditApplicationView()] });
    renderApp({ path: '/console/credit-applications' });
    await userEvent.click(await screen.findByRole('link', { name: 'app-fixture-1' }));
    await screen.findByRole('heading', { level: 1, name: 'app-fixture-1' });
    expect(screen.getByText('eligibility_assessments:asm-fixture-1')).toBeInTheDocument();
    expect(screen.getByText('conv-fixture-2')).toBeInTheDocument();
    expect(screen.getByText('Política sintética')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Resolver|Tomar/ })).toBeNull();
  });

  it('keeps customers and evaluators out of the agent console', async () => {
    startAuthServer({ session: sessionView({ role: 'evaluator' }) });
    startAgentServer();
    const { router } = renderApp({ path: '/console/inbox' });
    await waitFor(() => {
      expect(currentPath(router)).toBe('/console');
    });
  });
});
