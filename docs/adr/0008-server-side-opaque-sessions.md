# 0008: Server-side opaque sessions instead of JWT for the single-page app

- Status: accepted
- Date: 2026-09-27

## Context

The web client is a single-page app served from the same site as the API (phase 12). CLAUDE.md section 7 requires sessions with an idle expiry, an absolute expiry, rotation on privilege change, step-up for writes, revocation, and an httpOnly cookie. The session carries the customer identity that scopes every tool call and, through the unit of work, the row-level security context, so a forged or stale session is a direct path to another customer's data.

## Considered options

1. **Signed JWT in an httpOnly cookie.** Stateless verification, but revocation, idle expiry, and a step-up window that ends before the token does all need server state anyway (a deny list or a session table). A stolen token stays valid until it expires unless that state exists, and the payload grows with every claim added.
2. **Server-side sessions with opaque random tokens.** The client holds 256 random bits; the server stores only a digest and every mutable fact (last activity, step-up window, revocation).
3. **A third-party identity provider (OIDC).** The right choice for production, but out of reach for a hackathon prototype whose identities are synthetic personas.

## Decision

Option 2:

- The token is `secrets.token_urlsafe(32)`, returned to the client once. The `sessions` table stores its SHA-256 digest (`token_digest`, unique); lookups go by digest, and the raw token never enters the domain, logs, or the database.
- The `Session` domain model stores expiry instants (idle timeout, absolute expiry, step-up window end, revocation), and every expiry question is a pure function of the session and a `Clock` instant.
- Step-up is a privilege change, so it rotates the session: a new id and token in the same lineage; the old digest is retired and the old session revoked in one transaction. The absolute expiry is kept, so a step-up never extends a session.
- The session store runs under the `identity` database role, because a session is looked up before any customer context exists.
- Phase 11 puts the token in a `__Host-` prefixed, `HttpOnly`, `Secure`, `SameSite=Strict` cookie with double-submit CSRF protection.

## Consequences

- Revocation and logout take effect on the next request, with no deny list.
- Every request costs one indexed lookup and one update (the idle expiry slides); acceptable at prototype scale, and a cache can sit in front of the store later as a decorator.
- The API is stateful: several API instances must share the session store, which PostgreSQL already provides.
- A database leak exposes digests, not tokens; a stolen digest cannot be replayed as a cookie.
- Moving to OIDC later replaces the identity provider adapter; the session store and the rest of the design stay.
