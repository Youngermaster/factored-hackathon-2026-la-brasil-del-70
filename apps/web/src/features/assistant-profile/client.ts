import type { components } from '@/shared/api/generated/schema';

const API_ROOT = '/api/v1';

export type AssistantProfile = components['schemas']['AssistantProfileView'];
type Conversation = components['schemas']['ConversationView'];
type ConversationHistory = components['schemas']['ConversationHistoryResponse'];
type CsrfResponse = components['schemas']['CsrfResponse'];

export class ApiRequestError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined) headers.set('Content-Type', 'application/json');
  const response = await fetch(`${API_ROOT}${path}`, {
    ...init,
    credentials: 'include',
    headers,
  });
  if (!response.ok) {
    const problem: unknown = await response.json().catch(() => null);
    const message =
      typeof problem === 'object' &&
      problem !== null &&
      'title' in problem &&
      typeof problem.title === 'string'
        ? problem.title
        : 'Request failed';
    throw new ApiRequestError(response.status, message);
  }
  return (await response.json()) as T;
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const csrf = await request<CsrfResponse>('/auth/csrf');
  return request<T>(path, {
    method: 'POST',
    headers: { 'X-CSRF-Token': csrf.csrf_token },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
}

export function createConversation(): Promise<Conversation> {
  return post<Conversation>('/conversations');
}

export function getConversation(conversationId: string): Promise<ConversationHistory> {
  return request<ConversationHistory>(`/conversations/${encodeURIComponent(conversationId)}`);
}

export function getAssistantProfile(conversationId: string): Promise<AssistantProfile> {
  return request<AssistantProfile>(
    `/conversations/${encodeURIComponent(conversationId)}/assistant-profile`,
  );
}

export function changeAssistantName(
  conversationId: string,
  name: string,
): Promise<AssistantProfile> {
  return post<AssistantProfile>(
    `/conversations/${encodeURIComponent(conversationId)}/assistant-profile/name`,
    { name },
  );
}

export function mockAssistantImage(conversationId: string): Promise<AssistantProfile> {
  return post<AssistantProfile>(
    `/conversations/${encodeURIComponent(conversationId)}/assistant-profile/mock-image`,
  );
}
