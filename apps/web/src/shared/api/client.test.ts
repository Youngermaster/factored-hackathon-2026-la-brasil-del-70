import { http, HttpResponse } from 'msw';
import { describe, expect, it, vi } from 'vitest';

import { apiGet, apiPost, challenge, problem, sessionView, signedIn } from '@/test/msw/api';
import { server } from '@/test/msw/server';

import { createApiClient, CSRF_HEADER, REQUEST_ID_HEADER, unwrap } from './client';
import { ApiError, NetworkError } from './problem';

function recordRequests() {
  const seen: Request[] = [];
  server.events.on('request:start', ({ request }) => {
    seen.push(request.clone());
  });
  return seen;
}

describe('createApiClient', () => {
  it('sends the session cookie and a request id on every call', async () => {
    server.use(apiGet('/v1/auth/me', () => HttpResponse.json(sessionView())));
    const seen = recordRequests();
    const { client } = createApiClient();
    const session = await unwrap(client.GET('/v1/auth/me'));
    expect(session.role).toBe('customer');
    const me = seen.find((request) => request.url.endsWith('/v1/auth/me'));
    expect(me?.credentials).toBe('include');
    expect(me?.headers.get(REQUEST_ID_HEADER)).toMatch(/^[A-Za-z0-9-]{8,64}$/);
    expect(me?.headers.has(CSRF_HEADER)).toBe(false);
  });

  it('bootstraps the CSRF token once and sends it on unsafe calls', async () => {
    const csrfCalls = vi.fn();
    server.use(
      apiGet('/v1/auth/csrf', () => {
        csrfCalls();
        return HttpResponse.json({ csrf_token: 'csrf-anon' });
      }),
      apiPost('/v1/auth/start', ({ request }) =>
        request.headers.get(CSRF_HEADER) === 'csrf-anon'
          ? HttpResponse.json(challenge())
          : problem(403, 'csrf-token-invalid'),
      ),
    );
    const { client } = createApiClient();
    await unwrap(
      client.POST('/v1/auth/start', { body: { kind: 'persona', persona_id: 'acc-mx-accounts' } }),
    );
    await unwrap(
      client.POST('/v1/auth/start', { body: { kind: 'persona', persona_id: 'acc-mx-accounts' } }),
    );
    expect(csrfCalls).toHaveBeenCalledTimes(1);
  });

  it('adopts the rotated token from a login response', async () => {
    const tokens: (string | null)[] = [];
    server.use(
      apiPost('/v1/auth/verify', () => HttpResponse.json(signedIn(sessionView(), 'csrf-session'))),
      apiPost('/v1/auth/logout', ({ request }) => {
        tokens.push(request.headers.get(CSRF_HEADER));
        return HttpResponse.json({ csrf_token: 'csrf-after-logout' });
      }),
    );
    const { client, csrf } = createApiClient();
    await unwrap(
      client.POST('/v1/auth/verify', { body: { challenge_id: 'chl-1', code: '123456' } }),
    );
    await unwrap(client.POST('/v1/auth/logout'));
    expect(tokens).toEqual(['csrf-session']);
    expect(csrf.current).toBe('csrf-after-logout');
  });

  it('refreshes a rejected CSRF token and retries the call once', async () => {
    let tokenVersion = 0;
    server.use(
      apiGet('/v1/auth/csrf', () => {
        tokenVersion += 1;
        return HttpResponse.json({ csrf_token: `csrf-${String(tokenVersion)}` });
      }),
      apiPost('/v1/auth/step-up/start', ({ request }) =>
        request.headers.get(CSRF_HEADER) === 'csrf-2'
          ? HttpResponse.json(challenge({ purpose: 'step_up' }))
          : problem(403, 'csrf-token-invalid'),
      ),
    );
    const { client } = createApiClient();
    const result = await unwrap(client.POST('/v1/auth/step-up/start'));
    expect(result.purpose).toBe('step_up');
    expect(tokenVersion).toBe(2);
  });

  it('reports a lost session and forgets the CSRF token', async () => {
    const onUnauthorized = vi.fn();
    server.use(apiGet('/v1/auth/me', () => problem(401, 'session-expired')));
    const { client, csrf } = createApiClient({ onUnauthorized });
    csrf.set('old');
    await expect(unwrap(client.GET('/v1/auth/me'))).rejects.toMatchObject({
      slug: 'session-expired',
      status: 401,
    });
    expect(onUnauthorized).toHaveBeenCalledWith(expect.any(ApiError), '/v1/auth/me');
    expect(csrf.current).toBeNull();
  });

  it('does not treat a wrong code as a lost session', async () => {
    const onUnauthorized = vi.fn();
    server.use(apiPost('/v1/auth/verify', () => problem(401, 'verification-failed')));
    const { client } = createApiClient({ onUnauthorized });
    await expect(
      unwrap(client.POST('/v1/auth/verify', { body: { challenge_id: 'chl-1', code: '000000' } })),
    ).rejects.toMatchObject({ slug: 'verification-failed' });
    expect(onUnauthorized).not.toHaveBeenCalled();
  });

  it('turns a failed fetch into a NetworkError', async () => {
    server.use(http.get('*/v1/auth/me', () => HttpResponse.error()));
    const { client } = createApiClient();
    await expect(unwrap(client.GET('/v1/auth/me'))).rejects.toBeInstanceOf(NetworkError);
  });
});
