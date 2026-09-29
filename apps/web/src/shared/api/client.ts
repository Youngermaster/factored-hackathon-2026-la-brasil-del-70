import createClient, { type Client, type Middleware } from 'openapi-fetch';

import { CsrfStore } from './csrf';
import type { paths } from './generated/schema';
import { ApiError, NetworkError, toApiError } from './problem';

export type ApiClient = Client<paths>;

export interface ApiClientOptions {
  /** Same origin by default (the page's origin): Vite proxies /v1 in development and Caddy does in production. */
  readonly baseUrl?: string;
  readonly fetch?: typeof globalThis.fetch;
  /** Called on a 401 that means the session is gone (`authentication-required`, `session-expired`). */
  readonly onUnauthorized?: (error: ApiError, path: string) => void;
}

export interface ApiContextValue {
  readonly client: ApiClient;
  readonly csrf: CsrfStore;
}

export const CSRF_HEADER = 'X-CSRF-Token';
export const REQUEST_ID_HEADER = 'X-Request-ID';
const UNSAFE_METHODS = new Set(['POST', 'PUT', 'PATCH', 'DELETE']);

function newRequestId(): string {
  return crypto.randomUUID();
}

/** The one place a CSRF token may arrive in a body: login, step-up, logout, and the csrf endpoint. */
function readCsrfToken(body: unknown): string | null {
  if (typeof body === 'object' && body !== null && 'csrf_token' in body) {
    const token = body.csrf_token;
    return typeof token === 'string' ? token : null;
  }
  return null;
}

/**
 * The typed API client: openapi-fetch over the generated `paths`, with the session cookie (`credentials:
 * 'include'`), a request id on every call, the CSRF header on every unsafe call (bootstrapped from
 * `GET /v1/auth/csrf`, refreshed and retried once on `csrf-token-invalid`), and session loss reported to the app.
 */
export function createApiClient(options: ApiClientOptions = {}): ApiContextValue {
  const baseUrl = options.baseUrl ?? globalThis.location.origin;
  const doFetch = options.fetch ?? ((input, init) => globalThis.fetch(input, init));

  const csrf = new CsrfStore(async () => {
    const response = await doFetch(
      new Request(`${baseUrl}/v1/auth/csrf`, { credentials: 'include' }),
    );
    const body: unknown = await response.json().catch(() => null);
    const token = readCsrfToken(body);
    if (!response.ok || token === null) {
      throw toApiError(body, response);
    }
    return token;
  });

  const retryable = new Map<string, Request>();

  const middleware: Middleware = {
    async onRequest({ request, id }) {
      if (!request.headers.has(REQUEST_ID_HEADER)) {
        request.headers.set(REQUEST_ID_HEADER, newRequestId());
      }
      if (UNSAFE_METHODS.has(request.method)) {
        request.headers.set(CSRF_HEADER, await csrf.ensure());
        retryable.set(id, request.clone());
      }
      return request;
    },
    async onResponse({ request, response, id, schemaPath }) {
      const original = retryable.get(id);
      retryable.delete(id);
      if (response.ok && schemaPath.startsWith('/v1/auth/')) {
        const token = readCsrfToken(
          await response
            .clone()
            .json()
            .catch(() => null),
        );
        if (token !== null) {
          csrf.set(token);
        }
        return response;
      }
      if (response.status === 403 && original !== undefined) {
        const problem = toApiError(
          await response
            .clone()
            .json()
            .catch(() => null),
          response,
        );
        if (problem.slug === 'csrf-token-invalid') {
          const retry = new Request(original, { headers: new Headers(original.headers) });
          retry.headers.set(CSRF_HEADER, await csrf.refresh());
          return doFetch(retry);
        }
      }
      if (response.status === 401) {
        csrf.clear();
        const problem = toApiError(
          await response
            .clone()
            .json()
            .catch(() => null),
          response,
        );
        if (problem.slug === 'authentication-required' || problem.slug === 'session-expired') {
          options.onUnauthorized?.(problem, new URL(request.url).pathname);
        }
      }
      return response;
    },
    onError({ error }) {
      return error instanceof ApiError
        ? error
        : new NetworkError('network request failed', { cause: error });
    },
  };

  const client = createClient<paths>({ baseUrl, credentials: 'include', fetch: doFetch });
  client.use(middleware);
  return { client, csrf };
}

/** Returns the data of an openapi-fetch result, or throws its problem as a typed ApiError. */
export async function unwrap<T>(
  pending: Promise<{ data?: T; error?: unknown; response: Response }>,
): Promise<T> {
  const { data, error, response } = await pending;
  if (error !== undefined || !response.ok) {
    throw toApiError(error, response);
  }
  return data as T;
}
