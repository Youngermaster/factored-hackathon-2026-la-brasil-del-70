import {
  http,
  HttpResponse,
  type DefaultBodyType,
  type HttpResponseResolver,
  type PathParams,
} from 'msw';

import type { ProblemSlug, Schema } from '@/shared/api';

/**
 * MSW building blocks typed from the generated API schema: each fixture is a `Schema<...>` value, so a contract
 * change that breaks a fixture breaks the type check, and handlers answer with the real shapes.
 */
export const FIXED_NOW = new Date('2026-09-27T15:00:00Z');
const inMinutes = (minutes: number) =>
  new Date(FIXED_NOW.getTime() + minutes * 60_000).toISOString();

export function sessionView(overrides: Partial<Schema<'SessionView'>> = {}): Schema<'SessionView'> {
  return {
    role: 'customer',
    auth_level: 'otp_verified',
    step_up_valid: false,
    step_up_expires_at: null,
    idle_expires_at: inMinutes(15),
    absolute_expires_at: inMinutes(60),
    language_preference: 'es',
    ...overrides,
  };
}

export function challenge(
  overrides: Partial<Schema<'ChallengeResponse'>> = {},
): Schema<'ChallengeResponse'> {
  return {
    challenge_id: 'chl-login-1',
    purpose: 'login',
    expires_at: inMinutes(5),
    attempts_remaining: 5,
    delivery_channel: 'demo',
    demo_code: '482915',
    ...overrides,
  };
}

export function signedIn(
  session: Schema<'SessionView'> = sessionView(),
  csrf = 'csrf-session-1',
): Schema<'SignedInResponse'> {
  return { session, csrf_token: csrf };
}

/** A problem details response as the API sends it (application/problem+json, request id, Retry-After). */
export function problem(status: number, slug: ProblemSlug, extra: { retryAfter?: number } = {}) {
  const body: Schema<'ProblemDetails'> = {
    type: `https://bank-agent.local/problems/${slug}`,
    title: slug.replaceAll('-', ' '),
    status,
    instance: '/v1/test',
    request_id: 'req-test-0001',
  };
  return HttpResponse.json(body, {
    status,
    headers: {
      'Content-Type': 'application/problem+json',
      'X-Request-ID': 'req-test-0001',
      ...(extra.retryAfter === undefined ? {} : { 'Retry-After': String(extra.retryAfter) }),
    },
  });
}

type Resolver<Body extends DefaultBodyType> = HttpResponseResolver<
  PathParams,
  DefaultBodyType,
  Body
>;

export const apiGet = <Body extends DefaultBodyType>(
  path: `/v1/${string}`,
  resolver: Resolver<Body>,
) => http.get(`*${path}`, resolver);

export const apiPost = <Body extends DefaultBodyType>(
  path: `/v1/${string}`,
  resolver: Resolver<Body>,
) => http.post(`*${path}`, resolver);

/** The CSRF endpoint every unsafe call bootstraps from. */
export const csrfHandler = apiGet<Schema<'CsrfResponse'>>('/v1/auth/csrf', () =>
  HttpResponse.json({ csrf_token: 'csrf-anonymous-1' }),
);
