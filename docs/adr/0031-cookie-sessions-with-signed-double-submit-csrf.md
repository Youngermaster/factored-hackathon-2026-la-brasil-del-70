# 0031: Cookie sessions with signed double-submit CSRF for a same-site single-page app

- Status: accepted
- Date: 2026-09-27

The phase 11 prompt names this record ADR 0017; the human asked for the next free number, 0031.

## Context

[ADR 0008](0008-server-side-opaque-sessions.md) chose server-side opaque sessions. Phase 11 exposes them over HTTP to a single-page app (phase 12) that the production deployment serves from the same site as the API, behind Caddy (phase 16). CLAUDE.md section 7 requires `HttpOnly`, `Secure`, `SameSite=Strict` cookies with the `__Host-` prefix in production, a double-submit CSRF token on every state-changing request, rate limits per IP and per session, and the other HTTP guards. The frontend rules forbid tokens in web storage. The same app also needs a development setup over plain `http://localhost`.

A cookie session is sent by the browser automatically, which is what makes CSRF possible. `SameSite=Strict` already stops cross-site requests from carrying the cookie in current browsers, but it is not enough on its own: older or misconfigured clients, same-site subdomains, and top-level navigations are the known gaps.

## Considered options

1. **Bearer tokens in an `Authorization` header**, kept in memory by the SPA. No CSRF, but the token must live in JavaScript, where any injected script can read it, and a page reload loses it unless it is stored in web storage, which the frontend rules forbid.
2. **Cookie session plus a synchronizer token stored server side** per session. Strong, but every token check needs a store read, and a token must be fetched and rotated in step with the session.
3. **Cookie session plus a plain double-submit token** (a random cookie echoed in a header). Stateless, but a token that an attacker can plant in the cookie (from a sibling subdomain or over plain http) passes the check.
4. **Cookie session plus a signed double-submit token.** The token is a random nonce with an HMAC over the nonce and the session it belongs to, keyed by `CSRF_SECRET`. Stateless, and a planted token fails because it is not signed for the victim's session.

## Decision

Option 4, with these details:

- **Cookies.** Production: `__Host-session` (`HttpOnly`, `Secure`, `SameSite=Strict`, `Path=/`, no `Domain`, `Max-Age` equal to the time left to the session's absolute expiry) and `__Host-csrf` (the same flags without `HttpOnly`, so the SPA can read it). Development and test: `session` and `csrf` with the same flags except `Secure`, because the local servers speak plain http and the `__Host-` prefix requires `Secure`.
- **Token.** `<nonce>.<signature>`, where the nonce has 128 random bits and the signature is HMAC-SHA256 over `binding` and the nonce, with a key derived from `CSRF_SECRET`. The binding is the SHA-256 of the session token, or `anonymous` before login.
- **Check.** Every POST (every state-changing operation) needs `X-CSRF-Token` equal to the cookie, compared in constant time, and signed for the request's current session. Otherwise the answer is `403 csrf-token-invalid`. `GET /v1/auth/csrf` issues a token; login and step-up return a new one bound to the new session (rotation); logout returns an anonymous one.
- **Secret.** Production refuses to start without a strong `CSRF_SECRET`. Development without one signs with a random per-process secret, so tokens stop working on restart and the SPA fetches a new one.
- **Expired sessions.** An expired or revoked session is a `401` on every route; the engine never receives one. A new login resumes the conversation at its last safe state and asks again (the engine's re-sign-in rule), and a step-up keeps the session lineage, so a stepped-up turn continues directly.
- **Around it.** Rate limits per client IP and per session digest in an in-process sliding window (stricter for authentication), a 16 KiB body limit, a CORS allowlist with credentials only for listed origins (production refuses `*` and plain http), and the security headers on every response (a strict CSP with `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy: no-referrer`, a restrictive `Permissions-Policy`, HSTS in production).

## Consequences

- No token is ever readable by page scripts except the CSRF token, which proves nothing without the `HttpOnly` session cookie.
- CSRF checks cost one HMAC and no store read.
- The SPA must fetch `GET /v1/auth/csrf` before its first state-changing call and after any `401` or `csrf-token-invalid`, and must send `credentials: 'include'` and the header on every POST (phase 12's typed client does it once).
- Rotating `CSRF_SECRET` invalidates every issued token at once; clients recover by fetching a new one.
- The rate limiter counts per process, so several API workers each apply their own limits; a shared store is BACKLOG work for phase 16.
- A cross-site deployment (the SPA on another site) would break `SameSite=Strict` cookies; that would need a new decision.
