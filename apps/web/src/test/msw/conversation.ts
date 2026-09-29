import { HttpResponse } from 'msw';

import type { Schema } from '@/shared/api';

import { apiGet, apiPost, problem } from './api';
import { server } from './server';

/**
 * Fixtures and a scripted fake of `/v1/conversations`, typed from the generated schema. Tests are team-made and
 * synthetic: the ids, amounts, and texts below are fixtures, not organizer data.
 */
type Message = Schema<'AssistantMessage'>;
type TurnResponse = Schema<'TurnResponse'>;

const AT = '2026-09-29T15:00:00Z';

export function assistantMessage(overrides: Partial<Message> = {}): Message {
  return {
    text: 'Respuesta de prueba.',
    language: 'es',
    template_id: 'fixture.answer',
    notices: [],
    citations: [],
    action_statuses: [],
    balances: [],
    payment_statuses: [],
    card_status: [],
    credit_products: [],
    clarification: null,
    confirmation: null,
    card_action_confirmation: null,
    credit_intake_confirmation: null,
    eligibility: null,
    escalation: null,
    statement: null,
    step_up_required: false,
    ...overrides,
  };
}

export function conversationView(
  overrides: Partial<Schema<'ConversationView'>> = {},
): Schema<'ConversationView'> {
  return {
    conversation_id: 'conv-fixture-1',
    created_at: AT,
    updated_at: AT,
    language: null,
    state: 'START',
    status: 'active',
    workflow: { id: 'router', version: 1 },
    ...overrides,
  };
}

export function turnView(overrides: Partial<Schema<'TurnView'>> = {}): Schema<'TurnView'> {
  return {
    turn_id: 'turn-fixture-1',
    sequence: 1,
    customer_text: 'Hola',
    language: 'es',
    message: assistantMessage(),
    received_at: AT,
    completed_at: AT,
    ...overrides,
  };
}

/** One scripted answer: the message, and where the conversation ends up. */
export interface ScriptedTurn {
  readonly message: Message;
  readonly outcome?: Schema<'Outcome'>;
  readonly state?: string;
  readonly workflow?: Schema<'WorkflowRef'> | null;
}

export interface ConversationServerOptions {
  /** Answers in order; the last one repeats. */
  readonly script?: readonly (ScriptedTurn | ((text: string) => ScriptedTurn | Response))[];
  /** Existing conversations by id, for resume tests. */
  readonly histories?: Readonly<Record<string, Schema<'ConversationHistoryResponse'>>>;
  readonly traces?: Readonly<Record<string, Schema<'CustomerTraceResponse'>>>;
  /** When it returns false, conversation routes answer 401 (an expired session). */
  readonly signedIn?: () => boolean;
}

/** A stateful fake: creates conversations, answers turns from the script, and serves history and traces. */
export function startConversationServer(options: ConversationServerOptions = {}) {
  const histories = new Map(Object.entries(options.histories ?? {}));
  const sent: Schema<'SendTurnRequest'>[] = [];
  let answered = 0;
  const signedIn = options.signedIn ?? (() => true);
  const expired = () => problem(401, 'session-expired');

  server.use(
    apiPost('/v1/conversations', () => {
      if (!signedIn()) {
        return expired();
      }
      const conversation = conversationView({
        conversation_id: `conv-new-${String(histories.size + 1)}`,
      });
      histories.set(conversation.conversation_id, { conversation, turns: [] });
      return HttpResponse.json(conversation, { status: 201 });
    }),
    apiGet('/v1/conversations/:id', ({ params }) => {
      if (!signedIn()) {
        return expired();
      }
      const history = histories.get(String(params['id']));
      return history === undefined
        ? problem(404, 'resource-not-found')
        : HttpResponse.json(history);
    }),
    apiGet('/v1/conversations/:id/trace', ({ params }) => {
      const id = String(params['id']);
      return HttpResponse.json(options.traces?.[id] ?? { conversation_id: id, records: [] });
    }),
    apiPost('/v1/conversations/:id/turns', async ({ params, request }) => {
      if (!signedIn()) {
        return expired();
      }
      const id = String(params['id']);
      const body = (await request.json()) as Schema<'SendTurnRequest'>;
      sent.push(body);
      const script = options.script ?? [{ message: assistantMessage() }];
      const entry = script[Math.min(answered, script.length - 1)];
      answered += 1;
      const scripted = typeof entry === 'function' ? entry(body.text) : entry;
      if (scripted === undefined || scripted instanceof Response) {
        return scripted ?? problem(500, 'internal-error');
      }
      const response: TurnResponse = {
        conversation_id: id,
        turn_id: body.turn_id,
        message: scripted.message,
        outcome: scripted.outcome ?? 'resolved',
        state: scripted.state ?? 'RESOLVED',
        workflow:
          scripted.workflow === undefined
            ? { id: 'account_inquiry', version: 1 }
            : scripted.workflow,
        replayed: false,
      };
      return HttpResponse.json(response);
    }),
  );

  return {
    /** Every message the client sent, in order. */
    sent,
    histories,
  };
}
