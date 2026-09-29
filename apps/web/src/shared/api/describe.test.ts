import { afterEach, describe, expect, it, vi } from 'vitest';

import { errorMessageKey, errorRequestId } from './describe';
import { ApiError, NetworkError } from './problem';

const apiError = (status: number, type = 'about:blank') =>
  new ApiError({ status, type, title: 'x', requestId: 'req-00000001' });

afterEach(() => {
  vi.restoreAllMocks();
});

describe('errorMessageKey', () => {
  it('tells an offline device from an unreachable bank', () => {
    expect(errorMessageKey(new NetworkError('failed'))).toBe('errors.network');
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(false);
    expect(errorMessageKey(new NetworkError('failed'))).toBe('errors.offline');
  });

  it.each([
    [apiError(503), 'errors.server'],
    [
      apiError(503, 'https://bank-agent.local/problems/dependency-unavailable'),
      'errors.unavailable',
    ],
    [apiError(429), 'errors.rateLimited'],
    [apiError(403, 'https://bank-agent.local/problems/role-not-permitted'), 'errors.forbidden'],
    [apiError(404), 'errors.generic'],
    [new Error('bug'), 'errors.generic'],
  ])('maps %o to %s', (error, key) => {
    expect(errorMessageKey(error)).toBe(key);
  });

  it('exposes the request id of API errors only', () => {
    expect(errorRequestId(apiError(500))).toBe('req-00000001');
    expect(errorRequestId(new NetworkError('x'))).toBeUndefined();
  });
});
