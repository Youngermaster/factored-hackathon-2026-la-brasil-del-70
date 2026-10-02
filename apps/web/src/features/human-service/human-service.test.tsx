import { screen, waitFor, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';
import { axe } from 'vitest-axe';

import { queryKeys } from '@/shared/api';
import { currentPath, renderApp } from '@/test/app';
import { handoffView, startAgentServer } from '@/test/msw/agent';
import { apiGet, apiPost, problem, sessionView } from '@/test/msw/api';
import { startAuthServer } from '@/test/msw/auth';
import { conversationView, startConversationServer } from '@/test/msw/conversation';
import { humanServiceView } from '@/test/msw/human-service';
import { server } from '@/test/msw/server';

function queued() {
  startAuthServer({ session: sessionView() });
  return startConversationServer({
    histories: {
      'conv-fixture-1': { conversation: conversationView({ status: 'escalated' }), turns: [] },
    },
  });
}

describe('the persisted human exchange', () => {
  it('keeps the same conversation while queued and resumes a human-channel message after refresh', async () => {
    const chat = queued();
    const app = renderApp({ path: '/?conversation=conv-fixture-1' });
    await screen.findByRole('region', { name: 'Atención humana' }, { timeout: 5000 });
    expect(screen.queryByText('Tu caso ya está con una persona del equipo.')).toBeNull();
    await userEvent.type(
      screen.getByRole('textbox', { name: 'Tu mensaje' }),
      'Necesito explicar el cargo',
    );
    await userEvent.keyboard('{Enter}');
    await screen.findByText('Necesito explicar el cargo');
    await waitFor(() => {
      expect(chat.human.sent).toHaveLength(1);
    });
    expect(chat.sent).toHaveLength(0);
    expect(currentPath(app.router)).toBe('/?conversation=conv-fixture-1');
    expect(chat.human.messages.get('ho-fixture-1')).toHaveLength(1);
    app.unmount();
    renderApp({ path: '/?conversation=conv-fixture-1' });
    await screen.findByText('Necesito explicar el cargo');
  });

  it('reconnects from persisted history and keeps a closed thread readable', async () => {
    queued();
    let disconnected = false;
    let closed = false;
    const message = {
      message_id: 'msg-agent-1',
      handoff_id: 'ho-fixture-1',
      conversation_id: 'conv-fixture-1',
      role: 'agent' as const,
      sequence: 1,
      sent_at: '2026-09-29T15:01:00Z',
      text: 'Estoy revisando tu caso',
    };
    server.use(
      apiGet('/v1/conversations/:id/human-service', () =>
        disconnected
          ? HttpResponse.error()
          : HttpResponse.json(
              humanServiceView({
                status: closed ? 'closed' : 'joined',
                joined_at: message.sent_at,
                closed_at: closed ? message.sent_at : null,
                messages: [message],
              }),
            ),
      ),
    );
    const app = renderApp({ path: '/?conversation=conv-fixture-1' });
    await screen.findByText(message.text, {}, { timeout: 5000 });
    disconnected = true;
    await app.services.queryClient.invalidateQueries({ queryKey: queryKeys.humanService.all });
    await screen.findByText('Se perdió la conexión con el chat');
    expect(screen.getByText(message.text)).toBeInTheDocument();
    disconnected = false;
    closed = true;
    await userEvent.click(screen.getByRole('button', { name: 'Reintentar' }));
    await waitFor(() =>
      expect(screen.getByRole('textbox', { name: 'Tu mensaje' })).toHaveAttribute('readonly'),
    );
    expect(screen.getByText(message.text)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Nueva conversación' })).toBeEnabled();
  });

  it('loads successive cursor pages without dropping or duplicating messages', async () => {
    queued();
    const messages = Array.from({ length: 101 }, (_, i) => ({
      message_id: `msg-${String(i)}`,
      handoff_id: 'ho-fixture-1',
      conversation_id: 'conv-fixture-1',
      role: 'user' as const,
      sequence: i + 1,
      sent_at: '2026-09-29T15:01:00Z',
      text: `Fixture ${String(i)}`,
    }));
    const cursors: number[] = [];
    server.use(
      apiGet('/v1/conversations/:id/human-service', ({ request }) => {
        const after = Number(new URL(request.url).searchParams.get('after') ?? 0);
        cursors.push(after);
        return HttpResponse.json(
          humanServiceView({ messages: messages.filter((m) => m.sequence > after).slice(0, 100) }),
        );
      }),
    );
    renderApp({ path: '/?conversation=conv-fixture-1' });
    await screen.findByText('Fixture 100', {}, { timeout: 5000 });
    expect(
      within(screen.getByRole('log', { name: 'Mensajes con el agente' })).getAllByRole('listitem'),
    ).toHaveLength(101);
    expect(cursors).toContain(100);
  });

  it('allows an assigned agent to claim and reply', async () => {
    startAuthServer({ session: sessionView({ role: 'agent' }) });
    const agent = startAgentServer({ handoffs: [handoffView()] });
    agent.human.messages.set('ho-fixture-1', [
      {
        message_id: 'msg-customer',
        handoff_id: 'ho-fixture-1',
        conversation_id: 'conv-fixture-1',
        role: 'user',
        sequence: 1,
        sent_at: '2026-09-29T15:00:00Z',
        text: 'Necesito ayuda con el cargo',
      },
    ]);
    const app = renderApp({ path: '/console/inbox/ho-fixture-1' });
    await userEvent.click(await screen.findByRole('button', { name: 'Tomar traspaso' }));
    await userEvent.click(
      within(await screen.findByRole('dialog', { name: 'Tomar este traspaso' })).getByRole(
        'button',
        { name: 'Tomar' },
      ),
    );
    expect(await screen.findByText('Cliente')).toBeInTheDocument();
    await userEvent.type(
      await screen.findByRole('textbox', { name: 'Tu respuesta al cliente' }),
      'Puedo ayudarte con el caso',
    );
    await userEvent.click(screen.getByRole('button', { name: 'Enviar al cliente' }));
    await screen.findByText('Puedo ayudarte con el caso');
    expect(agent.human.sent).toHaveLength(1);
    expect(agent.human.messages.get('ho-fixture-1')?.at(-1)?.role).toBe('agent');
    const claimed = agent.handoffs.get('ho-fixture-1');
    if (claimed === undefined) throw new Error('missing handoff fixture');
    agent.handoffs.set(claimed.handoff_id, {
      ...claimed,
      status: 'resolved',
      resolution: {
        outcome: 'resolved_by_agent',
        note: 'Fixture',
        resolved_by: 'agent-demo-01',
        resolved_at: new Date().toISOString(),
      },
    });
    await app.services.queryClient.invalidateQueries({ queryKey: queryKeys.humanService.all });
    await waitFor(() => {
      expect(screen.queryByRole('textbox', { name: 'Tu respuesta al cliente' })).toBeNull();
    });
    await waitFor(() => {
      expect(screen.queryByRole('button', { name: 'Resolver' })).toBeNull();
    });
  });

  it('shows the creation quota without creating a phantom conversation', async () => {
    startAuthServer({ session: sessionView() });
    startConversationServer();
    server.use(
      apiPost('/v1/conversations', () =>
        problem(429, 'conversation-creation-limited', { retryAfter: 3600 }),
      ),
    );
    const app = renderApp();
    await screen.findByText(/cinco chats/i);
    expect(currentPath(app.router)).toBe('/');
  });

  it.each(['light', 'dark'] as const)(
    'keeps the queued exchange accessible in %s theme',
    async (theme) => {
      queued();
      const app = renderApp({ path: '/?conversation=conv-fixture-1', theme });
      await screen.findByRole('region', { name: 'Atención humana' }, { timeout: 5000 });
      expect(await axe(app.container)).toHaveNoViolations();
    },
  );
});
