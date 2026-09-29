/**
 * The double-submit CSRF token (ADR 0031), kept in memory only. It is bound to the session, so it changes on login,
 * step-up, and logout: the client stores the token from those responses and fetches a new one after a 401 or a
 * `csrf-token-invalid` problem.
 */
export class CsrfStore {
  private token: string | null = null;
  private pending: Promise<string> | null = null;
  private readonly fetchToken: () => Promise<string>;

  constructor(fetchToken: () => Promise<string>) {
    this.fetchToken = fetchToken;
  }

  get current(): string | null {
    return this.token;
  }

  set(token: string): void {
    this.token = token;
  }

  clear(): void {
    this.token = null;
  }

  /** The current token, fetching one first when there is none; concurrent callers share one request. */
  async ensure(): Promise<string> {
    if (this.token !== null) {
      return this.token;
    }
    this.pending ??= this.fetchToken().finally(() => {
      this.pending = null;
    });
    const token = await this.pending;
    this.token = token;
    return token;
  }

  async refresh(): Promise<string> {
    this.clear();
    return this.ensure();
  }
}
