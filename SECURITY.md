# Security policy

## Scope

This repository contains a hackathon prototype of a banking customer-service system. It runs on synthetic organizer data and team-generated fixtures only; no real customer data is processed. The following are in scope:

- the API service (`services/api`), including authentication, sessions, authorization, customer isolation, and policy enforcement;
- the web application (`apps/web`);
- the data platform, ML, and evaluation packages, where they handle credentials or data;
- the container, compose, and CI configuration;
- any secret, credential, or organizer data committed by mistake.

Out of scope: vulnerabilities in third-party services or dependencies that are already publicly known (report those upstream; our CI audits dependencies with pip-audit and pnpm audit), and findings that require physical access to a developer machine.

## Reporting a vulnerability

Do not open a public issue or pull request for a vulnerability.

1. Use GitHub's private vulnerability reporting for this repository (Security tab, "Report a vulnerability"), or contact a team maintainer directly through the private channel the team uses for the hackathon.
2. Include what you found, where (file, endpoint, or commit), how to reproduce it, and the impact you expect.
3. Never include real secrets, credentials, or personal data in the report. If you found an exposed secret, name its location and type, not its value.

The team acknowledges reports within two working days during the event, fixes confirmed issues with a regression test, and credits reporters who want to be credited.

## Handling secrets

- Credentials come only from environment variables; `.env` is gitignored and must never be committed, printed, or pasted into issues, chats, or model prompts.
- gitleaks runs in pre-commit and in CI over the full history.
- If a secret is committed, treat it as compromised: rotate it first, then remove it from the history with the team's agreement.
