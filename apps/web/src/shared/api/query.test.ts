import { describe, expect, it } from 'vitest';

import { ApiError, NetworkError } from './problem';
import { createQueryClient, DEFAULT_STALE_TIME_MS, queryKeys, shouldRetry } from './query';

const apiError = (status: number) => new ApiError({ status, type: 'about:blank', title: 'x' });

describe('shouldRetry', () => {
  it('retries network errors and 5xx, at most twice', () => {
    expect(shouldRetry(0, new NetworkError('offline'))).toBe(true);
    expect(shouldRetry(1, apiError(503))).toBe(true);
    expect(shouldRetry(2, apiError(503))).toBe(false);
  });

  it.each([400, 401, 403, 404, 409, 422, 429])('never retries a %i', (status) => {
    expect(shouldRetry(0, apiError(status))).toBe(false);
  });

  it('never retries a programming error', () => {
    expect(shouldRetry(0, new TypeError('bad'))).toBe(false);
  });
});

describe('createQueryClient', () => {
  it('applies the documented defaults', () => {
    const defaults = createQueryClient().getDefaultOptions();
    expect(defaults.queries?.staleTime).toBe(DEFAULT_STALE_TIME_MS);
    expect(defaults.queries?.retry).toBe(shouldRetry);
    expect(defaults.mutations?.retry).toBe(false);
  });
});

describe('queryKeys', () => {
  it('nests every key under its family so invalidation matches', () => {
    const family = queryKeys.conversations.all;
    const detail = queryKeys.conversations.detail('c-1');
    const trace = queryKeys.conversations.trace('c-1');
    expect(detail.slice(0, family.length)).toEqual(family);
    expect(trace.slice(0, detail.length)).toEqual(detail);
    expect(queryKeys.auth.session().slice(0, 2)).toEqual(queryKeys.auth.all);
    for (const key of [
      queryKeys.handoffs.list(),
      queryKeys.handoffs.detail('h-1'),
      queryKeys.creditApplications.detail('a-1'),
      queryKeys.evaluation.summaries(),
      queryKeys.evaluation.trace('c-1'),
    ]) {
      expect(key[0]).toBe(queryKeys.all[0]);
    }
  });

  it('keeps list filters in the key', () => {
    expect(queryKeys.handoffs.list({ status: 'open' })).toEqual([
      'api',
      'handoffs',
      'list',
      { status: 'open' },
    ]);
    expect(queryKeys.handoffs.list({ status: 'open' })).not.toEqual(queryKeys.handoffs.list());
  });
});
