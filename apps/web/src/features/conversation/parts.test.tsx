import { screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { describe, expect, it } from 'vitest';

import type { Schema } from '@/shared/api';
import { renderApp } from '@/test/app';
import { sessionView } from '@/test/msw/api';
import { DEMO_CODE, startAuthServer } from '@/test/msw/auth';
import {
  assistantMessage,
  startConversationServer,
  type ScriptedTurn,
} from '@/test/msw/conversation';

async function answer(script: ScriptedTurn[], locale: 'es-MX' | 'pt-BR' = 'es-MX') {
  startAuthServer({ session: sessionView() });
  const chat = startConversationServer({ script });
  renderApp({ path: '/', locale });
  const box = await screen.findByRole('textbox', { name: /Tu mensaje|Sua mensagem/ });
  await userEvent.type(box, 'Hola{Enter}');
  return chat;
}

const balance = (overrides: Partial<Schema<'BalanceView'>> = {}): Schema<'BalanceView'> => ({
  product_ref: 'products:prd-fixture-1',
  product_type: 'checking_account',
  masked_number: { last4: '6930' },
  current_balance: { amount: '3537.55', currency: 'MXN' },
  available_credit: null,
  credit_limit: null,
  over_limit: false,
  as_of: '2026-06-18T05:59:59Z',
  ...overrides,
});

describe('message parts', () => {
  it('shows every balance with its as-of date', async () => {
    await answer([
      {
        message: assistantMessage({
          text: 'Estos son tus saldos.',
          balances: [
            balance(),
            balance({
              product_ref: 'products:prd-fixture-2',
              product_type: 'credit_card',
              masked_number: { last4: '8807' },
              available_credit: { amount: '12000.00', currency: 'MXN' },
              credit_limit: { amount: '20000.00', currency: 'MXN' },
            }),
          ],
        }),
      },
    ]);
    const card = await screen.findByRole('region', { name: 'Saldos' });
    expect(within(card).getAllByText(/Datos al 18 jun 2026/)).toHaveLength(2);
    expect(within(card).getByText('Crédito disponible')).toBeInTheDocument();
    expect(within(card).getByText('8807')).toBeInTheDocument();
  });

  it('renders a Portuguese answer in Portuguese, with pt-BR formats, whatever the chrome language', async () => {
    await answer([
      {
        message: assistantMessage({
          text: 'Estes são os seus saldos.',
          language: 'pt',
          balances: [balance({ current_balance: { amount: '1234.50', currency: 'MXN' } })],
        }),
      },
    ]);
    const card = await screen.findByRole('region', { name: 'Saldos' });
    expect(within(card).getByText('Conta corrente')).toBeInTheDocument();
    expect(within(card).getByText('Final')).toBeInTheDocument();
    expect(within(card).getByText(/MX\$\s1\.234,50/)).toBeInTheDocument();
    expect(within(card).getByText(/Dados de 18 de jun\. de 2026/)).toBeInTheDocument();
  });

  it('keeps each currency of a statement on its own row and never adds them together', async () => {
    await answer([
      {
        message: assistantMessage({
          text: 'Este es el resumen de mayo.',
          statement: {
            as_of: '2026-06-18T05:59:59Z',
            period: {
              dates: { start: '2026-05-01', end: '2026-05-31' },
              product_ref: 'products:prd-fixture-1',
            },
            totals: [
              {
                currency: 'MXN',
                debits: { amount: '1500.00', currency: 'MXN' },
                credits: { amount: '200.00', currency: 'MXN' },
                debit_count: 3,
                credit_count: 1,
              },
              {
                currency: 'USD',
                debits: { amount: '40.00', currency: 'USD' },
                credits: { amount: '0.00', currency: 'USD' },
                debit_count: 1,
                credit_count: 0,
              },
            ],
            lines: [],
            sources: [],
            transaction_count: 6,
            not_settled_count: 1,
            unclassified_count: 0,
            truncated: false,
          },
        }),
      },
    ]);
    const totals = await screen.findByRole('table', { name: 'Totales por moneda' });
    const rows = within(totals).getAllByRole('row').slice(1);
    expect(rows.map((row) => within(row).getAllByRole('cell')[0]?.textContent)).toEqual([
      'MXN',
      'USD',
    ]);
    expect(within(totals).getByText(/1,500\.00/)).toBeInTheDocument();
    expect(within(totals).getByText(/40\.00/)).toBeInTheDocument();
    expect(within(totals).queryByText(/1,540/)).toBeNull();
    expect(screen.getByText(/Del 1 may 2026 al 31 may 2026/)).toBeInTheDocument();
  });

  it('blocks a card through step-up and reports it only once verified', async () => {
    const chat = await answer([
      {
        message: assistantMessage({
          text: 'Voy a bloquear tu tarjeta. ¿Confirmas?',
          card_action_confirmation: {
            action: 'block',
            card_last4: '8807',
            reason: 'lost',
            planned_actions: ['block_card'],
          },
        }),
        outcome: 'in_progress',
      },
      {
        message: assistantMessage({
          text: 'Necesito una verificación reforzada.',
          step_up_required: true,
        }),
        outcome: 'in_progress',
      },
      {
        message: assistantMessage({
          text: 'Bloqueamos tu tarjeta y lo comprobamos en los registros.',
          action_statuses: [
            {
              action: 'block_card',
              status: 'verified',
              reference: null,
              evidence: 'products:prd-fixture-2',
            },
          ],
        }),
      },
    ]);
    const card = await screen.findByRole('region', { name: 'Revisa el cambio en tu tarjeta' });
    expect(within(card).getByText('Bloqueo preventivo')).toBeInTheDocument();
    expect(within(card).getByText('Pérdida')).toBeInTheDocument();
    expect(screen.queryByText('Verificado')).toBeNull();
    await userEvent.click(within(card).getByRole('button', { name: 'Confirmar' }));
    const dialog = await screen.findByRole('dialog');
    await userEvent.type(
      await within(dialog).findByRole('textbox', { name: 'Código de verificación' }),
      DEMO_CODE,
    );
    await userEvent.click(within(dialog).getByRole('button', { name: 'Verificar' }));
    const action = await screen.findByRole('region', { name: 'Bloquear la tarjeta' });
    expect(within(action).getByText('Verificado')).toBeInTheDocument();
    expect(chat.sent.map((turn) => turn.text)).toEqual([
      'Hola',
      'Sí, confirmo',
      'Listo, ya confirmé mi identidad',
    ]);
  });

  it('moves the quoted policy text under the cited policies', async () => {
    await answer([
      {
        message: assistantMessage({
          text: 'Tu respuesta.\n\nTexto de la cláusula.',
          citations: [{ clause: 'ACC-ALL-1@1', excerpt: 'Texto de la cláusula.' }],
        }),
      },
    ]);
    const answerText = await screen.findByText('Tu respuesta.');
    expect(answerText.textContent).toBe('Tu respuesta.');
    expect(screen.getByText('1 política citada')).toBeInTheDocument();
    expect(screen.getByText('ACC-ALL-1@1')).toBeInTheDocument();
  });

  it('labels credit products as synthetic and indicative, with their catalog names', async () => {
    await answer([
      {
        message: assistantMessage({
          text: 'Estos son los préstamos.',
          credit_products: [
            {
              product_code: 'MX-PL-STANDARD',
              display_name: 'Préstamo personal Estándar',
              product_type: 'personal_loan',
              jurisdiction: 'MX',
              currency: 'MXN',
              min_amount: { amount: '10000.00', currency: 'MXN' },
              max_amount: { amount: '350000.00', currency: 'MXN' },
              min_term_months: 6,
              max_term_months: 60,
              min_annual_rate: '28.00',
              max_annual_rate: '65.00',
              purposes: ['general_purpose'],
              required_information: ['declared_monthly_income'],
              eligibility_clause_ids: [],
              self_service_eligibility: true,
              catalog_version: 'synthetic-catalog-fixture',
              synthetic: true,
            },
          ],
        }),
      },
    ]);
    const product = await screen.findByRole('region', { name: /Préstamo personal Estándar/ });
    expect(within(product).getByText('Catálogo sintético')).toBeInTheDocument();
    expect(within(product).getByText(/No es una oferta/)).toBeInTheDocument();
    expect(within(product).getByText('De 6 a 60 meses')).toBeInTheDocument();
  });
});
