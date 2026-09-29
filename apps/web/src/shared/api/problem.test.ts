import { describe, expect, it } from 'vitest';

import { ApiError, hasProblem, isApiError, NetworkError, toApiError } from './problem';

const response = (status: number, headers: Record<string, string> = {}) =>
  new Response(null, { status, headers });

describe('toApiError', () => {
  it('reads a problem document into a typed error', () => {
    const error = toApiError(
      {
        type: 'https://bank-agent.local/problems/identity-locked',
        title: 'Identity locked',
        status: 429,
        instance: '/v1/auth/verify',
        request_id: 'req-1234abcd',
      },
      response(429, { 'Retry-After': '900' }),
    );
    expect(error).toBeInstanceOf(ApiError);
    expect(error.slug).toBe('identity-locked');
    expect(error.status).toBe(429);
    expect(error.requestId).toBe('req-1234abcd');
    expect(error.retryAfterSeconds).toBe(900);
    expect(hasProblem(error, 'identity-locked', 'rate-limited')).toBe(true);
    expect(hasProblem(error, 'session-expired')).toBe(false);
  });

  it('lists the invalid fields of a validation error without their values', () => {
    const error = toApiError(
      {
        type: 'https://bank-agent.local/problems/validation-error',
        title: 'Validation error',
        status: 422,
        instance: '/v1/auth/start',
        errors: [{ loc: ['body', 'phone_last4'], type: 'string_pattern_mismatch' }, 'garbage'],
      },
      response(422),
    );
    expect(error.slug).toBe('validation-error');
    expect(error.invalidFields).toEqual(['body.phone_last4']);
  });

  it('marks an unknown problem type as unknown', () => {
    const error = toApiError(
      { type: 'https://example.org/other', title: 'Other', status: 409 },
      response(409),
    );
    expect(error.slug).toBe('unknown');
  });

  it('still types a response that is not a problem document', () => {
    const error = toApiError(
      '<html>Bad gateway</html>',
      new Response(null, {
        status: 502,
        statusText: 'Bad Gateway',
        headers: { 'X-Request-ID': 'req-gw-000001' },
      }),
    );
    expect(error.status).toBe(502);
    expect(error.title).toBe('Bad Gateway');
    expect(error.slug).toBe('unknown');
    expect(error.requestId).toBe('req-gw-000001');
    expect(error.retryAfterSeconds).toBeUndefined();
  });

  it('ignores a malformed Retry-After and an empty status text', () => {
    const error = toApiError(null, response(503, { 'Retry-After': 'soon' }));
    expect(error.retryAfterSeconds).toBeUndefined();
    expect(error.title).toBe('HTTP error');
  });
});

describe('error guards', () => {
  it('tell API errors from network errors', () => {
    expect(isApiError(new NetworkError('offline'))).toBe(false);
    expect(hasProblem(new Error('x'), 'conflict')).toBe(false);
    expect(new NetworkError('offline').name).toBe('NetworkError');
  });
});
