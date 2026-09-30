# Demo mode on the public demo

The public judging demo runs with `DEMO_MODE=true`: when someone signs in (or steps up before a write), the one-time code comes back in the API response and the web app shows it on screen, labeled as a demo. This page records why, what it exposes, how it is contained, and what a real deployment does instead.

## Why it exists

- The system has no real delivery channel for one-time codes (no SMS or email provider, and no real customers to send them to). The mock identity service (`adapters/identity`) generates, hashes, and checks codes exactly as a real one would; only the delivery is simulated (`DemoOtpSender`).
- Judges must be able to sign in as the demo personas (`docs/demo/personas.md`) and play every path, writes with step-up included, without a phone.
- The brief asks for identity from "a trusted test session or identity service"; demo mode is that test session, visible as such.

## How production allows it

| Setting | Effect |
|---|---|
| `DEMO_MODE=true` | The API returns the code in the challenge; the persona picker is offered |
| `ALLOW_PUBLIC_DEMO_MODE=true` | Required in production for the line above; without it the API refuses to start (`bootstrap/settings.py`, tests in `tests/unit/bootstrap/test_settings.py`) |
| `VITE_DEMO_MODE=true` | Build-time switch of the web image: the persona picker and the on-screen code |

The API logs `public_demo_mode` as a warning at every start (`asgi.warn_about_public_demo_mode`). Nothing else changes: the code is still hashed at rest, expires in 5 minutes, allows 5 attempts, and step-up is still required before every write.

## What it exposes

- **Anyone can sign in as any demo persona.** Identification by persona id or by document number plus phone digits is a demo convenience; with the code on screen, the second factor proves nothing about the person at the keyboard. Every persona is a synthetic customer from the organizer's synthetic delivery (seeded from the committed, pseudonymized sample), so no real person's data is reachable.
- **Anyone can perform the demo writes** a persona allows: a protective card block, a dispute case, a credit application intake. They change only the synthetic demo database; no money moves and no lending decision exists anywhere in the system.
- **The agent and evaluator consoles are reachable** through the staff personas (`agent-demo-01`, `evaluator-demo-01`), including the evaluator trace with internal risk estimates of the synthetic credit profiles. They are part of what the judges evaluate.

## How it is contained

- Synthetic data only (`docs/security/data-use.md`); the seed never loads real identifiers.
- Customer isolation is unchanged: a persona sees only its own records; another customer's resource is a 404 (the smoke test probes it on the deployed URL).
- Rate limits are shared by every worker and keyed by the real client address (Caddy's `X-Forwarded-For`, trusted from Caddy only): 10 authentication requests per minute per address and per session by default.
- The model budget caps spend per session, per conversation, and per day; at 100 percent the service answers from templates (degradation level L2).
- The retention purge deletes conversation text after 7 days and ended sessions after 7 days (`docs/security/data-retention.md`).
- The demo is taken down after 2026-10-16 (`deploy/prod.sh destroy --yes` deletes the database volume).
- Demo writes can be reset: `deploy/prod.sh seed` restores blocked cards; a fresh volume resets everything.

## What a real deployment does instead

1. `DEMO_MODE=false` and no `ALLOW_PUBLIC_DEMO_MODE`; the persona picker is not built (`VITE_DEMO_MODE=false`).
2. A real `OtpSender` adapter delivers codes to the phone or email on file through a provider, never in the response; delivery failures and resend limits are part of the flow.
3. Identification starts from the bank's own authenticated channel (an app session, a signed-in web banking session) rather than a persona id, and the one-time code is a step-up, not the only factor.
4. Staff consoles sit behind the bank's single sign-on, on a separate origin or network.
5. Alerting on sign-in failure rates per address and per subject, in addition to the lockout.

The BACKLOG row "Replace `DemoOtpSender` with a real delivery adapter for any non-demo deployment" tracks item 2.
