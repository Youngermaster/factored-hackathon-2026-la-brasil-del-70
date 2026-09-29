import { describe, expect, it } from 'vitest';

import { escalationTurnFixture, mvpHandlers, profileFixture, renameTurnFixture } from './msw/mvp';
import { server } from './msw/server';

const API = 'http://localhost';

describe('Tuesday MVP fixtures', () => {
  it('serve the profile, a new conversation, and an account answer', async () => {
    server.use(...mvpHandlers);

    const profile = await fetch(`${API}/v1/profile`);
    expect(await profile.json()).toEqual(profileFixture);

    const created = await fetch(`${API}/v1/conversations`, { method: 'POST' });
    expect(created.status).toBe(201);
    const { conversation_id: conversationId } = (await created.json()) as {
      conversation_id: string;
    };

    const reply = await fetch(`${API}/v1/conversations/${conversationId}/turns`, {
      method: 'POST',
    });
    const body = (await reply.json()) as {
      message: { balances: unknown[] };
      correlation_id: string;
    };
    expect(body.message.balances).toHaveLength(1);
    expect(body.correlation_id).toMatch(/^[A-Za-z0-9-]{8,64}$/);
  });

  it('label the simulated agent and pair it with a handoff', () => {
    const agent = escalationTurnFixture.message.simulated_agent;
    expect(agent?.simulated).toBe(true);
    expect(escalationTurnFixture.message.escalation).toBeTruthy();
  });

  it('return the changed assistant profile only on the turn that changed it', () => {
    expect(renameTurnFixture.assistant_profile?.name).toBe('Sol');
    expect(escalationTurnFixture.assistant_profile).toBeUndefined();
  });
});
