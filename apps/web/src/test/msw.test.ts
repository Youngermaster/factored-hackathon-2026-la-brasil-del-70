import { http, HttpResponse } from 'msw';
import { describe, expect, it } from 'vitest';

import { server } from './msw/server';

const API = 'http://localhost/health/live';

describe('MSW test server', () => {
  it('serves the default handler', async () => {
    const response = await fetch(API);

    expect(response.status).toBe(200);
    expect(await response.json()).toEqual({ status: 'live' });
  });

  it('lets a test override a handler', async () => {
    server.use(http.get('*/health/live', () => new HttpResponse(null, { status: 503 })));

    const response = await fetch(API);

    expect(response.status).toBe(503);
  });

  it('restores the default handler after an override', async () => {
    const response = await fetch(API);

    expect(response.status).toBe(200);
  });

  it('rejects requests that have no handler', async () => {
    await expect(fetch('http://localhost/api/unhandled')).rejects.toThrow();
  });
});
