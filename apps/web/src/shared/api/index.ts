export { ApiProvider } from './ApiProvider';
export {
  createApiClient,
  CSRF_HEADER,
  REQUEST_ID_HEADER,
  unwrap,
  type ApiClient,
  type ApiClientOptions,
  type ApiContextValue,
} from './client';
export { useApi } from './context';
export { errorMessageKey, errorRequestId, type ErrorMessageKey } from './describe';
export { CsrfStore } from './csrf';
export type { components, operations, paths } from './generated/schema';
export {
  ApiError,
  hasProblem,
  isApiError,
  NetworkError,
  toApiError,
  type ProblemDetails,
  type ProblemSlug,
} from './problem';
export { createQueryClient, DEFAULT_STALE_TIME_MS, queryKeys, shouldRetry } from './query';

import type { components } from './generated/schema';

/** Shorthand for a generated schema type: `Schema<'SessionView'>`. */
export type Schema<Name extends keyof components['schemas']> = components['schemas'][Name];
