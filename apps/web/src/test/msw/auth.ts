import { HttpResponse } from 'msw';

import type { Schema } from '@/shared/api';

import { apiGet, apiPost, challenge, problem, sessionView, signedIn } from './api';
import { server } from './server';

export const DEMO_CODE = '482915';

type Role = Schema<'Role'>;

function roleOf(identification: unknown): Role {
  if (
    typeof identification === 'object' &&
    identification !== null &&
    'persona_id' in identification
  ) {
    const id = String(identification.persona_id);
    if (id.startsWith('agent-')) {
      return 'agent';
    }
    if (id.startsWith('evaluator-')) {
      return 'evaluator';
    }
  }
  return 'customer';
}

/**
 * A stateful fake of `/v1/auth` for integration tests, answering with the generated schema's shapes: a login opens
 * a challenge, the demo code signs in (persona ids starting with agent- or evaluator- get those roles), step-up
 * opens a window, logout ends the session. It records every request so tests can check headers.
 */
export function startAuthServer(initial: { session?: Schema<'SessionView'> | null } = {}) {
  const state = {
    session: initial.session ?? null,
    pendingRole: 'customer' as Role,
    expired: false,
  };
  const lost = () => problem(401, state.expired ? 'session-expired' : 'authentication-required');
  const requests: Request[] = [];
  server.events.on('request:start', ({ request }) => {
    requests.push(request.clone());
  });

  server.use(
    apiGet('/v1/auth/me', () =>
      state.session === null ? lost() : HttpResponse.json(state.session),
    ),
    apiPost('/v1/auth/start', async ({ request }) => {
      state.pendingRole = roleOf(await request.json());
      return HttpResponse.json(challenge());
    }),
    apiPost('/v1/auth/verify', async ({ request }) => {
      const body = (await request.json()) as Schema<'VerifyLoginRequest'>;
      if (body.code !== DEMO_CODE) {
        return problem(401, 'verification-failed');
      }
      state.expired = false;
      state.session = sessionView({
        role: state.pendingRole,
        language_preference: body.language ?? null,
      });
      return HttpResponse.json(signedIn(state.session, 'csrf-session'));
    }),
    apiPost('/v1/auth/step-up/start', () =>
      state.session === null
        ? lost()
        : HttpResponse.json(challenge({ challenge_id: 'chl-step-up-1', purpose: 'step_up' })),
    ),
    apiPost('/v1/auth/step-up/verify', async ({ request }) => {
      const body = (await request.json()) as Schema<'VerifyStepUpRequest'>;
      if (state.session === null) {
        return lost();
      }
      if (body.code !== DEMO_CODE) {
        return problem(401, 'verification-failed');
      }
      state.session = {
        ...state.session,
        auth_level: 'step_up',
        step_up_valid: true,
        step_up_expires_at: new Date(Date.now() + 5 * 60_000).toISOString(),
      };
      return HttpResponse.json(signedIn(state.session, 'csrf-stepped-up'));
    }),
    apiPost('/v1/auth/logout', () => {
      state.session = null;
      return HttpResponse.json({ csrf_token: 'csrf-anonymous-2' });
    }),
  );
  return {
    state,
    requests,
    /** Ends the session on the server side, as an idle expiry would. */
    expire() {
      state.session = null;
      state.expired = true;
    },
  };
}
