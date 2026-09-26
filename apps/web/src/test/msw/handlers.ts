import { http, HttpResponse } from 'msw';

/**
 * Default handlers shared by every test. Features add their own handlers next to their code, typed from the
 * generated API types (phase 12), and override these per test with `server.use(...)`.
 */
export const handlers = [http.get('*/health/live', () => HttpResponse.json({ status: 'live' }))];
