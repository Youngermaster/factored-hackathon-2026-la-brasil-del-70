import { HttpResponse } from 'msw';

import type { Schema } from '@/shared/api';

import { apiGet, apiPost, problem } from './api';
import { server } from './server';

export function humanServiceView(
  overrides: Partial<Schema<'HumanServiceResponse'>> = {},
): Schema<'HumanServiceResponse'> {
  return {
    conversation_id: 'conv-fixture-1',
    handoff_id: 'ho-fixture-1',
    status: 'queued',
    queued_at: '2026-09-29T15:00:00Z',
    joined_at: null,
    closed_at: null,
    messages: [],
    ...overrides,
  };
}

/** Synthetic persisted exchanges; the lifecycle is derived from the fixture's handoff, not the transport. */
export function startHumanServiceServer(
  side: 'customer' | 'agent',
  lookup: (id: string) => Schema<'HumanServiceResponse'> | null,
) {
  const messages = new Map<string, Schema<'HumanMessage'>[]>();
  const sent: Schema<'SendHumanMessageRequest'>[] = [];
  const path =
    side === 'customer'
      ? '/v1/conversations/:id/human-service'
      : '/v1/agent/handoffs/:id/human-service';
  server.use(
    apiGet(path, ({ params, request }) => {
      const view = lookup(String(params['id']));
      if (view === null) return problem(404, 'resource-not-found');
      const after = Number(new URL(request.url).searchParams.get('after') ?? 0);
      return HttpResponse.json({
        ...view,
        messages: (messages.get(view.handoff_id) ?? view.messages)
          .filter((m) => m.sequence > after)
          .slice(0, 100),
      });
    }),
    apiPost(`${path}/messages`, async ({ params, request }) => {
      const view = lookup(String(params['id']));
      if (view === null) return problem(404, 'resource-not-found');
      const body = (await request.json()) as Schema<'SendHumanMessageRequest'>;
      sent.push(body);
      const history = messages.get(view.handoff_id) ?? [...view.messages];
      const existing = history.find((m) => m.message_id === body.message_id);
      if (existing !== undefined) return HttpResponse.json({ message: existing, replayed: true });
      if (view.status === 'closed') return problem(409, 'invalid-state-transition');
      const message: Schema<'HumanMessage'> = {
        ...body,
        handoff_id: view.handoff_id,
        conversation_id: view.conversation_id,
        sequence: history.length + 1,
        role: side === 'customer' ? 'user' : 'agent',
        sent_at: new Date().toISOString(),
      };
      messages.set(view.handoff_id, [...history, message]);
      return HttpResponse.json({ message, replayed: false });
    }),
  );
  return { messages, sent };
}
