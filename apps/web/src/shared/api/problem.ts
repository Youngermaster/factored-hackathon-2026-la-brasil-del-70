import type { components } from './generated/schema';

export type ProblemDetails = components['schemas']['ProblemDetails'];

/** The problem types the API documents (docs/api/README.md, "Error types"), by the slug at the end of `type`. */
export type ProblemSlug =
  | 'authentication-required'
  | 'session-expired'
  | 'verification-failed'
  | 'code-expired'
  | 'csrf-token-invalid'
  | 'role-not-permitted'
  | 'step-up-required'
  | 'action-not-permitted'
  | 'resource-not-found'
  | 'conflict'
  | 'invalid-state-transition'
  | 'payload-too-large'
  | 'validation-error'
  | 'unprocessable-request'
  | 'rate-limited'
  | 'conversation-creation-limited'
  | 'identity-locked'
  | 'service-unavailable'
  | 'dependency-unavailable'
  | 'internal-error';

const KNOWN_SLUGS: ReadonlySet<string> = new Set<ProblemSlug>([
  'authentication-required',
  'session-expired',
  'verification-failed',
  'code-expired',
  'csrf-token-invalid',
  'role-not-permitted',
  'step-up-required',
  'action-not-permitted',
  'resource-not-found',
  'conflict',
  'invalid-state-transition',
  'payload-too-large',
  'validation-error',
  'unprocessable-request',
  'rate-limited',
  'conversation-creation-limited',
  'identity-locked',
  'service-unavailable',
  'dependency-unavailable',
  'internal-error',
]);

/** An RFC 9457 problem from the API, typed. `slug` is `unknown` for a type this client does not know. */
export class ApiError extends Error {
  override readonly name = 'ApiError';
  readonly status: number;
  readonly slug: ProblemSlug | 'unknown';
  readonly type: string;
  readonly title: string;
  readonly requestId: string | undefined;
  readonly invalidFields: readonly string[];
  /** From `Retry-After` on 429 and lockouts, in seconds. */
  readonly retryAfterSeconds: number | undefined;

  constructor(init: {
    status: number;
    type: string;
    title: string;
    requestId?: string | undefined;
    invalidFields?: readonly string[];
    retryAfterSeconds?: number | undefined;
  }) {
    super(`${String(init.status)} ${init.title}`);
    this.status = init.status;
    this.type = init.type;
    this.title = init.title;
    const slug = init.type.split('/').pop() ?? '';
    this.slug = KNOWN_SLUGS.has(slug) ? (slug as ProblemSlug) : 'unknown';
    this.requestId = init.requestId;
    this.invalidFields = init.invalidFields ?? [];
    this.retryAfterSeconds = init.retryAfterSeconds;
  }
}

/** The request never got an HTTP answer (offline, DNS, CORS, aborted). Retried by the query client. */
export class NetworkError extends Error {
  override readonly name = 'NetworkError';
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function retryAfter(response: Response): number | undefined {
  const header = response.headers.get('Retry-After');
  if (header === null) {
    return undefined;
  }
  const seconds = Number(header);
  return Number.isFinite(seconds) && seconds >= 0 ? seconds : undefined;
}

/**
 * Builds an ApiError from an error body (already parsed by openapi-fetch) and its response. A body that is not a
 * problem document (a proxy error page, an empty body) still yields a typed error with the HTTP status.
 */
export function toApiError(body: unknown, response: Response): ApiError {
  const requestId = response.headers.get('X-Request-ID') ?? undefined;
  if (isRecord(body) && typeof body['type'] === 'string' && typeof body['title'] === 'string') {
    const errors = Array.isArray(body['errors']) ? body['errors'] : [];
    const invalidFields = errors
      .map((entry: unknown) =>
        isRecord(entry) && Array.isArray(entry['loc']) ? entry['loc'].join('.') : null,
      )
      .filter((field): field is string => field !== null);
    return new ApiError({
      status: typeof body['status'] === 'number' ? body['status'] : response.status,
      type: body['type'],
      title: body['title'],
      requestId: typeof body['request_id'] === 'string' ? body['request_id'] : requestId,
      invalidFields,
      retryAfterSeconds: retryAfter(response),
    });
  }
  return new ApiError({
    status: response.status,
    type: 'about:blank',
    title: response.statusText === '' ? 'HTTP error' : response.statusText,
    requestId,
    retryAfterSeconds: retryAfter(response),
  });
}

export function isApiError(error: unknown): error is ApiError {
  return error instanceof ApiError;
}

export function hasProblem(error: unknown, ...slugs: ProblemSlug[]): error is ApiError {
  return error instanceof ApiError && (slugs as string[]).includes(error.slug);
}
