import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { currentPath, renderApp } from '@/test/app';
import { sessionView } from '@/test/msw/api';
import { DEMO_CODE, startAuthServer } from '@/test/msw/auth';
import {
  assistantMessage,
  conversationView,
  startConversationServer,
  turnView,
} from '@/test/msw/conversation';

async function openChat(path = '/') {
  const auth = startAuthServer({ session: sessionView() });
  const view = renderApp({ path });
  await screen.findByRole('heading', { level: 1, name: 'Asistente' });
  return { auth, ...view };
}

async function say(text: string) {
  const box = screen.getByRole('textbox', { name: 'Tu mensaje' });
  await userEvent.type(box, text);
  await userEvent.keyboard('{Enter}');
}

async function completeStepUp() {
  const dialog = await screen.findByRole('dialog');
  await userEvent.type(
    await within(dialog).findByRole('textbox', { name: 'Código de verificación' }),
    DEMO_CODE,
  );
  await userEvent.click(within(dialog).getByRole('button', { name: 'Verificar' }));
}

const disputeConfirmation = assistantMessage({
  text: 'Voy a abrir una aclaración por este cargo. ¿Confirmas?',
  confirmation: {
    amount: { amount: '1250.00', currency: 'MXN' },
    card_last4: '4821',
    expected_resolution_by: '2026-11-13',
    merchant_display: 'FIXTURE MARKET',
    occurred_on: '2026-06-15',
    planned_actions: ['create_dispute_case'],
    reason: 'unrecognized',
  },
});

describe('the customer chat', () => {
  it('runs the normal dispute path through confirmation, step-up, and a verified case', async () => {
    const chat = startConversationServer({
      script: [
        { message: disputeConfirmation, outcome: 'in_progress', state: 'CONFIRM' },
        {
          message: assistantMessage({
            text: 'Necesito una verificación reforzada.',
            step_up_required: true,
          }),
          outcome: 'in_progress',
          state: 'EXECUTE',
        },
        {
          message: assistantMessage({
            text: 'Abrimos tu aclaración y lo comprobamos en los registros.',
            action_statuses: [
              {
                action: 'create_dispute_case',
                status: 'verified',
                reference: 'dispute_cases:case-fixture-9',
                evidence: 'dispute_cases:case-fixture-9',
              },
            ],
          }),
        },
      ],
    });
    const { router } = await openChat();
    await say('No reconozco un cargo de 1250 pesos en FIXTURE MARKET');

    const card = await screen.findByRole('region', {
      name: 'Revisa la aclaración antes de confirmar',
    });
    expect(within(card).getByText('Terminada en')).toBeInTheDocument();
    expect(within(card).getByText('4821')).toBeInTheDocument();
    expect(within(card).getByText('Abrir un caso de aclaración')).toBeInTheDocument();
    expect(currentPath(router)).toBe('/?conversation=conv-new-1');

    await userEvent.click(within(card).getByRole('button', { name: 'Confirmar' }));
    await completeStepUp();

    const action = await screen.findByRole('region', { name: 'Abrir un caso de aclaración' });
    expect(within(action).getByText('Verificado')).toBeInTheDocument();
    // The case reference and the read-back evidence both name the verified record.
    expect(within(action).getAllByText('dispute_cases:case-fixture-9')).toHaveLength(2);
    expect(chat.sent.map((turn) => turn.text)).toEqual([
      'No reconozco un cargo de 1250 pesos en FIXTURE MARKET',
      'Sí, confirmo',
      'Listo, ya confirmé mi identidad',
    ]);
  });

  it('sends the chosen option as an ordinal and keeps the option id on the button', async () => {
    const chat = startConversationServer({
      script: [
        {
          message: assistantMessage({
            text: 'Encontré dos compras parecidas. ¿Cuál es?',
            clarification: {
              options: [
                {
                  option_id: 'opt-1',
                  amount: { amount: '300.00', currency: 'MXN' },
                  card_last4: '4821',
                  merchant_display: 'FIXTURE CAFE',
                  occurred_on: '2026-06-10',
                },
                {
                  option_id: 'opt-2',
                  amount: { amount: '310.00', currency: 'MXN' },
                  card_last4: '4821',
                  merchant_display: 'FIXTURE CAFE',
                  occurred_on: '2026-06-12',
                },
              ],
            },
          }),
          outcome: 'clarified',
        },
        { message: assistantMessage({ text: 'Perfecto, la segunda.' }) },
      ],
    });
    await openChat();
    await say('No reconozco una compra en FIXTURE CAFE');
    const second = await screen.findByRole('button', { name: /Opción 2: FIXTURE CAFE/ });
    expect(second).toHaveAttribute('data-option-id', 'opt-2');
    await userEvent.click(second);
    await screen.findByText('Perfecto, la segunda.');
    expect(chat.sent.at(-1)?.text).toBe('Opción 2');
    // Only the latest answer's buttons act: the options of the earlier answer are now disabled.
    expect(screen.getByRole('button', { name: /Opción 1: FIXTURE CAFE/ })).toBeDisabled();
  });

  it('shows a failed action as a failure, never as success', async () => {
    startConversationServer({
      script: [
        {
          message: assistantMessage({
            text: 'No pudimos bloquear la tarjeta. Pasamos tu caso a una persona.',
            action_statuses: [
              { action: 'block_card', status: 'failed', reference: null, evidence: null },
            ],
          }),
          outcome: 'escalated',
        },
      ],
    });
    await openChat();
    await say('Bloquea mi tarjeta');
    const action = await screen.findByRole('region', { name: 'Bloquear la tarjeta' });
    expect(within(action).getByText('Falló')).toBeInTheDocument();
    expect(within(action).getByText(/No se pudo completar/)).toBeInTheDocument();
    expect(within(action).queryByText('Verificado')).toBeNull();
    expect(action.querySelector('[data-status="verified"]')).toBeNull();
  });

  it('shows the escalation notice with the handoff reference and the expected time', async () => {
    startConversationServer({
      script: [
        {
          message: assistantMessage({
            text: 'Voy a pasar tu conversación a una persona del equipo.',
            escalation: {
              handoff_id: 'ho-fixture-7',
              expected_response_by: '2026-09-30T15:00:00Z',
            },
          }),
          outcome: 'escalated',
          state: 'ESCALATED',
        },
      ],
    });
    await openChat();
    await userEvent.click(screen.getByRole('button', { name: 'Hablar con una persona' }));
    const notice = await screen.findByRole('region', {
      name: 'Tu caso pasó a una persona del equipo',
    });
    expect(within(notice).getByText('ho-fixture-7')).toBeInTheDocument();
    expect(within(notice).getByText(/30 sep 2026, 3:00/)).toBeInTheDocument();
    expect(
      await screen.findByText('Tu caso ya está con una persona del equipo.'),
    ).toBeInTheDocument();
    expect(screen.getByText('Quiero hablar con una persona')).toBeInTheDocument();
  });

  it('caps the message at 2,000 characters with a visible counter', async () => {
    startConversationServer();
    await openChat();
    const box = screen.getByRole('textbox', { name: 'Tu mensaje' });
    expect(screen.getByText('0 de 2000')).toBeInTheDocument();
    await userEvent.click(box);
    await userEvent.paste('a'.repeat(2050));
    expect(box).toHaveValue('a'.repeat(2000));
    expect(screen.getByText('2000 de 2000')).toBeInTheDocument();
    expect(screen.getByText('Llegaste al límite de 2000 caracteres.')).toBeInTheDocument();
  });

  it('keeps Shift+Enter as a new line and sends on Enter', async () => {
    const chat = startConversationServer();
    await openChat();
    const box = screen.getByRole('textbox', { name: 'Tu mensaje' });
    await userEvent.type(box, 'Hola{Shift>}{Enter}{/Shift}qué tal');
    expect(box).toHaveValue('Hola\nqué tal');
    expect(chat.sent).toHaveLength(0);
    await userEvent.keyboard('{Enter}');
    await screen.findByText('Respuesta de prueba.');
    expect(chat.sent[0]?.text).toBe('Hola\nqué tal');
    expect(box).toHaveValue('');
  });

  it('offers a retry after a network failure and resends the same turn', async () => {
    let calls = 0;
    const chat = startConversationServer({
      script: [
        () => {
          calls += 1;
          return calls === 1
            ? HttpResponse.error()
            : { message: assistantMessage({ text: 'Ya llegó.' }) };
        },
      ],
    });
    await openChat();
    await say('Hola');
    expect(await screen.findByText(/Tu mensaje no se envió/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    await screen.findByText('Ya llegó.');
    expect(chat.sent).toHaveLength(2);
    expect(chat.sent[1]?.turn_id).toBe(chat.sent[0]?.turn_id);
    expect(screen.queryByText(/Tu mensaje no se envió/)).toBeNull();
  });

  it('says nothing changed when the customer cancels the step-up, and offers it again', async () => {
    startConversationServer({
      script: [
        {
          message: assistantMessage({
            text: 'Necesito una verificación reforzada.',
            step_up_required: true,
          }),
          outcome: 'in_progress',
        },
      ],
    });
    await openChat();
    await say('Sí');
    const dialog = await screen.findByRole('dialog');
    await userEvent.click(await within(dialog).findByRole('button', { name: 'Cancelar' }));
    expect(
      await screen.findByText('No confirmaste tu identidad, así que no hicimos ningún cambio.'),
    ).toBeInTheDocument();
    await userEvent.click(screen.getByRole('button', { name: 'Confirmar identidad' }));
    expect(await screen.findByRole('dialog')).toBeInTheDocument();
  });

  it('resumes a conversation from the address', async () => {
    startConversationServer({
      histories: {
        'conv-old': {
          conversation: conversationView({ conversation_id: 'conv-old', status: 'active' }),
          turns: [
            turnView({
              customer_text: '¿Cuál es mi saldo?',
              message: assistantMessage({ text: 'Tu saldo es este.' }),
            }),
          ],
        },
      },
    });
    await openChat('/?conversation=conv-old');
    expect(await screen.findByText('¿Cuál es mi saldo?')).toBeInTheDocument();
    expect(screen.getByText('Tu saldo es este.')).toBeInTheDocument();
    expect(screen.getByText('conv-old')).toBeInTheDocument();
  });

  it('explains a conversation it cannot find and starts a new one', async () => {
    startConversationServer();
    const { router } = await openChat('/?conversation=conv-missing');
    expect(await screen.findByText('No encontramos esa conversación')).toBeInTheDocument();
    const [fromNotice] = screen.getAllByRole('button', { name: 'Nueva conversación' });
    await userEvent.click(fromNotice ?? document.body);
    await waitFor(() => {
      expect(currentPath(router)).toBe('/?conversation=conv-new-1');
    });
  });

  it('fills the message box from a topic without sending', async () => {
    const chat = startConversationServer();
    await openChat();
    await userEvent.click(screen.getByRole('button', { name: /Crédito/ }));
    expect(screen.getByRole('textbox', { name: 'Tu mensaje' })).toHaveValue(
      '¿Qué préstamos personales tienen?',
    );
    expect(chat.sent).toHaveLength(0);
  });
});
