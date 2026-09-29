/**
 * Validates a post-login destination taken from the URL, so `next` can never send the browser to another origin
 * (an open redirect). Only same-app absolute paths are accepted: `/`, `/console`, `/?conversation=abc`.
 */
export function safeNextPath(candidate: string | null | undefined, fallback: string): string {
  if (candidate === null || candidate === undefined || candidate === '') {
    return fallback;
  }
  if (!candidate.startsWith('/') || candidate.startsWith('//') || candidate.includes('\\')) {
    return fallback;
  }
  try {
    const url = new URL(candidate, 'http://app.invalid');
    if (url.origin !== 'http://app.invalid' || url.pathname.startsWith('/login')) {
      return fallback;
    }
    return `${url.pathname}${url.search}`;
  } catch {
    return fallback;
  }
}
