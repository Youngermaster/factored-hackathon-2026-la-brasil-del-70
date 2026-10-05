# 0045: Expose Grafana read-only under /grafana

- Status: accepted
- Date: 2026-10-05
- Amends: [ADR 0036](0036-grafana-live-analytics-separate-from-offline-evaluation.md) ("Production binds it to loopback, disables anonymous access, requires the Grafana login, and is reached through the documented SSH tunnel"). The separation between live telemetry and offline evaluation that ADR 0036 decided is unchanged.
- Builds on: [ADR 0035](0035-telemetry-export-and-degradation-ladder.md) (the telemetry pipeline and the degradation ladder), [ADR 0019](0019-single-host-compose-deployment.md) (one host, Caddy at the edge), and [ADR 0038](0038-continuous-deployment-to-azure-with-github-actions.md) (continuous deployment runs `deploy/prod.sh release`).

## Context

The live dashboards answer questions the judges ask of a production system: how fast the service answers, how often it fails, what the model costs per turn, when it degrades, and why it hands conversations to people. Under ADR 0036 they were reachable only through an SSH tunnel, so nobody outside the team could open them. Opening Grafana changes what it may show and who may query it:

- The Jaeger datasource (never working with Jaeger 2.21) would let any Grafana user read traces through the datasource proxy, and the server spans held the client's IP address, port, and user agent for seven days.
- Grafana's frontend runs script. Served from the bank's origin, a flaw in Grafana could act with a visitor's bank session.
- Continuous deployment never touched the `obs` profile (`OBS=1` had to be in the caller's environment), so a Grafana change merged to `main` never reached the VM.

## Considered options

1. **SSH tunnel only (ADR 0036 as written).** Best isolation and no work. Judges cannot see the dashboards, so the operational evidence stays private.
2. **A separate host name** (a second public IP with its own Azure DNS label and its own Caddy site, or a second DNS label in front of the same IP). A separate origin and host-only cookies: script on Grafana's pages can never reach the bank's cookies or API. Needs an Azure resource or DNS change, a certificate, and a change to the network security group, on the final day.
3. **The same origin at the sub-path `/grafana/`, with the bank's cookies stripped** before a request reaches Grafana. One Caddy snippet behind a switch, no Azure change, the same certificate. Grafana's script runs on the bank's origin.
4. **A hosted Grafana** (Grafana Cloud or Azure Managed Grafana) reading Prometheus remotely. Strong isolation, but Prometheus would have to be reachable from the internet or remote-write its data out, which adds an account, a credential, and an egress path for operational data.

## Decision

Option 3 for the event, with option 2 recorded as the production follow-up.

- Caddy serves Grafana at `<PUBLIC_ORIGIN>/grafana/` when `GRAFANA_ROUTE=on` (default `off`), through the same `import name-{$VAR:default}` pattern the TLS modes use. `/grafana` redirects to `/grafana/` (308); `/grafana/*` is proxied to `grafana:3000` with the prefix kept (`GF_SERVER_SERVE_FROM_SUB_PATH=true`); `/grafana/metrics` answers 404 and Grafana's own metrics endpoint is off. With the route off, `/grafana` is an unknown SPA path.
- Every cookie with the `__Host-` or `__Secure-` prefix is removed from requests to Grafana. The bank sets only `__Host-session` and `__Host-csrf` in production, so Grafana never receives a bank cookie; Grafana's cookies (`grafana_session`, `grafana_session_expiry`) have neither prefix and pass. A unit test runs the rule against the production cookie names.
- Caddy adds no CSP on the Grafana route: browsers enforce every CSP header they receive, so the SPA's strict policy would break Grafana, and Grafana's needs must never loosen the SPA's policy. Grafana sends its own (`GF_SECURITY_CONTENT_SECURITY_POLICY`), its default template without external hosts or websockets and with `frame-ancestors 'none'`. Caddy adds HSTS, `Referrer-Policy: same-origin`, `Permissions-Policy`, COOP, and `X-Robots-Tag: noindex`.
- Grafana is hardened: secure, `SameSite=Strict` cookies; sign-up, organisation creation, viewer editing, basic auth, snapshots, public dashboards, Live, Gravatar, embedding, the news feed, update checks, and plugin downloads off; sessions expire after 1 hour idle and 12 hours in total.
- **Anonymous viewing** is a second switch, `GRAFANA_ANONYMOUS_VIEWER` (default `false`). When true, visitors are Viewers of the main organisation: they see the provisioned dashboards and cannot edit, save, or open Explore. The admin login with the Key Vault password (`grafana-admin-password`) stays. The provisioned dashboards are read-only (`allowUiUpdates: false`).
- Grafana's only datasource is Prometheus; the Jaeger datasource is deleted by provisioning. Traces stay in the Jaeger UI on the SSH tunnel. The collector deletes `client.address`, `client.port`, `user_agent.original`, and their pre-stable equivalents from spans and metrics before anything is stored.
- Prometheus bounds what one query may cost: `--query.timeout=30s`, `--query.max-samples=5000000`, `--query.max-concurrency=4`, and it runs without the admin and lifecycle APIs.
- Grafana and Caddy share a new internal network, `observability`, which nothing else joins. Grafana keeps its loopback port for the tunnel; its memory limit rises from 384 MB to 512 MB.
- `deploy/prod.sh` reads `OBS` from the server env file when the caller does not set it, so every release (continuous deployment included) recreates the `obs` services whose configuration changed. It refuses `GRAFANA_ROUTE` and `GRAFANA_ANONYMOUS_VIEWER` values that Caddy or Grafana would not understand, because an unknown snippet name stops Caddy from starting.
- A third dashboard, **Bank agent: service health** (`bank-agent-service`), is Grafana's home page.

## Consequences

- Anyone with the link sees live latency, error, model, degradation, handoff, and host metrics, labelled as live telemetry and separate from the offline evaluation (ADR 0036).
- **Same-origin risk.** Script on a `/grafana/` page runs on the bank's origin. A cross-site scripting flaw in Grafana could read the `__Host-csrf` cookie (readable by script by design of the double-submit scheme) and call `/v1/*` with the visitor's session cookie. It needs a person with a live bank session to open a malicious Grafana page in the same browser. Mitigations: no editors and no user-created content, plugin downloads off, Live, snapshots, and public dashboards off, Grafana's own CSP, Grafana never receives the bank's cookies, Grafana's cookie has path `/grafana` so the API never sees it, `frame-ancestors 'none'` on both surfaces, and the route switch turns it all off without a new image. The residual risk is accepted for the event; a separate host name (option 2) removes it.
- **Anonymous viewers can send any PromQL** through the datasource, bounded by the Prometheus limits above, and see safety-intervention counts, which give an attacker coarse feedback on injection attempts. Labels are the catalog's bounded ids and codes only: no message text, amounts, identifiers, or traces. Grafana stores one anonymous device row per browser.
- The cookie rule depends on every bank cookie carrying the `__Host-` or `__Secure-` prefix. A new unprefixed bank cookie would reach Grafana; the unit test fails first if a production cookie name loses its prefix.
- Grafana's root URL is the public one, so through the tunnel the address is `http://localhost:3000/grafana/`. Its cookies are `Secure`; browsers accept them on `http://localhost`.
- The single-file bind mounts of the collector and Prometheus keep the file a container started with: after a merge that changes them, those two containers need one restart (the release recreates only services whose compose configuration changed).
- Host metrics come from the collector's own `/proc`, which is not namespaced in a container: CPU, load, memory, disk I/O, and root filesystem usage describe the VM without the Docker socket or a host mount. Network counters are left out, because `/proc/net/dev` shows the container's interface. Per-container resources are not observed.

## Production delta

What changes on the VM after this merges, and what the operator runs (it is not automatic):

| Item | Before | After |
|---|---|---|
| Server env file | no `OBS`, `GRAFANA_ROUTE`, `GRAFANA_ANONYMOUS_VIEWER` | `OBS=1`, `GRAFANA_ROUTE=on`, `GRAFANA_ANONYMOUS_VIEWER=true` (a human decision: judges open the dashboards without credentials) |
| `obs` profile | started by hand with `OBS=1`, never recreated by releases | managed by every `deploy/prod.sh up` and release |
| Public `/grafana/` | the SPA's not-found page | Grafana, anonymous Viewer, admin login available |
| Grafana datasources | Prometheus and a broken Jaeger | Prometheus only |
| Traces | client address, port, user agent stored 7 days | removed in the collector |
| Prometheus | no query limits | 30 s timeout, 5 million samples, 4 concurrent queries |
| Grafana memory limit | 384 MB | 512 MB |

Rollback: set `GRAFANA_ROUTE=off` (and `GRAFANA_ANONYMOUS_VIEWER=false`) in the env file and run `deploy/prod.sh up`; Caddy closes the route on recreation. A failed release restores the previous commit, whose `prod.sh` ignores the env file's `OBS` and whose Caddyfile has no route, while the running Grafana is left untouched.
