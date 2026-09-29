import { http, HttpResponse } from 'msw';

import type { Schema } from '@/shared/api';

import { apiGet, apiPost, csrfHandler, problem } from './api';

const defaultConversation: Schema<'ConversationView'> = {
  conversation_id: 'conv-default',
  created_at: '2026-09-29T15:00:00Z',
  updated_at: '2026-09-29T15:00:00Z',
  language: null,
  state: 'START',
  status: 'active',
  workflow: { id: 'router', version: 1 },
};
const defaultProfile: Schema<'AssistantProfileView'> = {
  assistant_name: 'Assistant',
  avatar_key: 'avatar_1',
  avatar_url: '/v1/assistant-profile/avatars/avatar_1.png',
  updated_at: null,
};

/**
 * Default handlers shared by every test. Features add their own handlers next to their code, typed from the
 * generated API types (src/test/msw/api.ts), and override these per test with `server.use(...)`.
 */
export const handlers = [
  http.get('*/health/live', () => HttpResponse.json({ status: 'live' })),
  csrfHandler,
  apiPost('/v1/conversations', () => HttpResponse.json(defaultConversation, { status: 201 })),
  apiGet('/v1/conversations/:id/assistant-profile', () => HttpResponse.json(defaultProfile)),
  apiGet('/v1/conversations/:id/trace', ({ params }) =>
    HttpResponse.json({ conversation_id: String(params['id']), records: [] }),
  ),
  apiGet('/v1/conversations/:id', () => problem(404, 'resource-not-found')),
];
