# 0019: A single-host Docker Compose deployment for the event, with a documented path to managed services

- Status: accepted
- Date: 2026-09-29
- Update (2026-10-04): [ADR 0038](0038-continuous-deployment-to-azure-with-github-actions.md) amends the image decision below for continuous deployment: the workflow builds the images, pushes them to GHCR, and the VM pulls them by digest. Building on the VM stays for local and manual use. [ADR 0037](0037-cloud-secret-management-with-azure-key-vault.md) replaces the env file as the secret store on Azure.

Phase 16 decision, taken by the session under the orchestrator's pre-approval (the human delegated the plan-mode approval); the plan is `docs/plans/phase-16.md`. The hosting provider is undecided on purpose ("decide later"), so the decision is host-neutral.

## Context

The submission needs a public link to the working system, kept up until the award ceremony on 2026-10-16. The traffic is judges and the team, a few concurrent people at most, over synthetic data, with the demo one-time codes shown on screen. The system is an API with two to four worker processes, a static single-page app, PostgreSQL with forced row-level security and a non-superuser owner, one-shot owner jobs (migrations, the seed, the retention purge), and optional telemetry services. The team has days, not weeks, one operator, and no cloud account chosen yet. Whatever runs must enforce the security standards of CLAUDE.md section 7 (TLS, `__Host-` cookies, CSP, least-privilege database roles, container hardening) and must not depend on a provider's managed features to be secure.

## Considered options

1. **One VM running the whole stack with Docker Compose** (Caddy with automatic TLS, the API, PostgreSQL on an internal network, the jobs, optional telemetry), built from the repository on the VM. Works the same on AWS Lightsail, EC2, an Azure VM, or any Linux host with Docker; every control lives in the repository and is tested locally with the same files; cost is one small VM; the operator runs a handful of commands. The VM is a single point of failure, backups are the operator's job, and scaling past one machine needs a redesign.
2. **Managed services per tier**: a container service (ECS Fargate, App Runner, Azure Container Apps) for the API, managed PostgreSQL (RDS, Azure Database for PostgreSQL), object storage and a CDN for the SPA, a managed secrets store, and a load balancer with managed certificates. Better availability, automated backups, and scaling; but it ties the design to a provider the team has not chosen, needs an account, IAM, networking, and infrastructure-as-code the team has no time to write and test, and moves security controls (TLS termination, headers, database roles on a managed superuser model) into provider configuration that cannot be verified locally before the deadline.
3. **A platform as a service** (Render, Fly.io, Railway): quick to start, but a third party holds the database and the logs of a banking demo, the free tiers sleep, and the role and header controls depend on each platform's features.

## Decision

Option 1. `deploy/compose.prod.yml` runs the stack on one VM, `deploy/prod.sh` operates it (build, up, seed, update, backup, restore, rollback, take down), and `deploy/README.md` gives the host-neutral steps with concrete sections for AWS Lightsail (recommended: the simplest firewall, fixed monthly price, static IP), EC2, and an Azure VM. Images are built on the VM from the checked-out commit and tagged with it; nothing is pushed to a registry. The whole stack, TLS included (Caddy's local CA), was verified locally with the local model before any host exists.

## Consequences

- Every security control is in the repository, reviewed, and tested (`services/api/tests/unit/test_deploy_config.py`, the non-superuser owner suite, the smoke test, the browser CSP check), so a host change does not change the security posture.
- Availability is one VM: a host failure takes the demo down until it is recreated from the repository and the latest backup (`deploy/prod.sh restore`). Backups are manual or a host cron line; the guide says how.
- Two API workers share rate limits and the model budget through PostgreSQL, so the design already runs more than one process; a second VM would need a shared PostgreSQL and a load balancer in front of the Caddy instances.
- Secrets live in one mode-600 env file on the VM, delivered by the operator; rotation is an edit and a restart (the guide lists which secret needs a re-seed).

## Migration path to production (remaining deployment work, phase 17)

1. PostgreSQL to a managed service with the same roles: a non-superuser owner, the application role, point-in-time recovery; migrations stay a one-off job.
2. The API image to a container service with two or more tasks behind a load balancer; the load balancer terminates TLS and forwards to the tasks, and `FORWARDED_ALLOW_IPS` names the load balancer's subnet.
3. The SPA to object storage and a CDN with the same headers (the CSP needs a per-response nonce, so an edge function or keeping Caddy in front of the static files).
4. Secrets from a managed secrets store injected as environment variables (pydantic-settings reads the environment only).
5. A real one-time-code channel (SMS or email) instead of demo mode, multi-region only if the business needs it, and Kubernetes only if several services appear. None of these is needed for the event.
