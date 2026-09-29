import { ApiError, errorMessageKey, type ErrorMessageKey } from '@/shared/api';

export type CodeErrorKey = ErrorMessageKey | 'auth.wrongCode' | 'auth.codeExpired' | 'auth.locked';

export interface CodeError {
  readonly key: CodeErrorKey;
  /** Minutes until a lockout ends (from Retry-After). */
  readonly minutes?: number;
  readonly requestId?: string | undefined;
  /** The code cannot be used any more: offer a new one. */
  readonly needsNewCode: boolean;
}

/** Turns a failed verify (login or step-up) into the message the code step shows. */
export function describeCodeError(error: unknown): CodeError {
  if (error instanceof ApiError) {
    if (error.slug === 'verification-failed') {
      return { key: 'auth.wrongCode', needsNewCode: false, requestId: error.requestId };
    }
    if (error.slug === 'code-expired') {
      return { key: 'auth.codeExpired', needsNewCode: true, requestId: error.requestId };
    }
    if (error.slug === 'identity-locked') {
      return {
        key: 'auth.locked',
        minutes: Math.max(1, Math.ceil((error.retryAfterSeconds ?? 900) / 60)),
        needsNewCode: true,
        requestId: error.requestId,
      };
    }
  }
  return {
    key: errorMessageKey(error),
    needsNewCode: false,
    requestId: error instanceof ApiError ? error.requestId : undefined,
  };
}
