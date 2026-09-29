/** The sign-in URL after a lost session, keeping where the person was (the conversation id included). */
export function expiredLoginPath(pathname: string, search: string): string {
  return `/login?reason=expired&next=${encodeURIComponent(`${pathname}${search}`)}`;
}
