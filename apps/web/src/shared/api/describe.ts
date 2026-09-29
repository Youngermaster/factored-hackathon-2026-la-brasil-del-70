import { ApiError, NetworkError } from './problem';

/** The locale key of the plain-language message for a failed call that the screen does not handle itself. */
export type ErrorMessageKey =
  'errors.network' | 'errors.server' | 'errors.rateLimited' | 'errors.forbidden' | 'errors.generic';

export function errorMessageKey(error: unknown): ErrorMessageKey {
  if (error instanceof NetworkError) {
    return 'errors.network';
  }
  if (error instanceof ApiError) {
    if (error.status >= 500) {
      return 'errors.server';
    }
    if (error.status === 429) {
      return 'errors.rateLimited';
    }
    if (error.slug === 'role-not-permitted') {
      return 'errors.forbidden';
    }
  }
  return 'errors.generic';
}

/** The request id to show next to an error, so support can find the log line. */
export function errorRequestId(error: unknown): string | undefined {
  return error instanceof ApiError ? error.requestId : undefined;
}
