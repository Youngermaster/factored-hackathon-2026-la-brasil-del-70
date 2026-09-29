import { describe, expect, it, vi } from 'vitest';

import { CsrfStore } from './csrf';

describe('CsrfStore', () => {
  it('fetches once for concurrent callers and then reuses the token', async () => {
    const fetchToken = vi.fn(() => Promise.resolve('t-1'));
    const store = new CsrfStore(fetchToken);
    expect(store.current).toBeNull();
    await expect(Promise.all([store.ensure(), store.ensure()])).resolves.toEqual(['t-1', 't-1']);
    await store.ensure();
    expect(fetchToken).toHaveBeenCalledTimes(1);
  });

  it('replaces the token when a login or step-up rotates it, and refreshes on demand', async () => {
    const fetchToken = vi.fn().mockResolvedValueOnce('t-1').mockResolvedValueOnce('t-2');
    const store = new CsrfStore(fetchToken);
    store.set('rotated');
    await expect(store.ensure()).resolves.toBe('rotated');
    await expect(store.refresh()).resolves.toBe('t-1');
    store.clear();
    await expect(store.ensure()).resolves.toBe('t-2');
  });

  it('lets a failed fetch be retried', async () => {
    const fetchToken = vi
      .fn()
      .mockRejectedValueOnce(new Error('down'))
      .mockResolvedValueOnce('t-3');
    const store = new CsrfStore(fetchToken);
    await expect(store.ensure()).rejects.toThrow('down');
    await expect(store.ensure()).resolves.toBe('t-3');
  });
});
