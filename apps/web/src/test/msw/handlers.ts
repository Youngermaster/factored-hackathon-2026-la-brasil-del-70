import { http, HttpResponse } from 'msw';

import { csrfHandler } from './api';

/**
 * Default handlers shared by every test. Features add their own handlers next to their code, typed from the
 * generated API types (src/test/msw/api.ts), and override these per test with `server.use(...)`.
 */
export const handlers = [
  http.get('*/health/live', () => HttpResponse.json({ status: 'live' })),
  csrfHandler,
];
