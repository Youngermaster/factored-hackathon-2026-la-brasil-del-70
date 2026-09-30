---
name: ux-backend-start
description: Start the whole local product (PostgreSQL, the API, and the web UX) from any machine state and open it in the browser. It inspects first and runs only the missing steps (Docker, configuration, data pipeline, seed, migrations, containers), and delegates to the setup-postgres-data, download-organizer-data, and github-collaboration skills when their conditions apply. Use it when someone asks to start, run, open, or set up the app, the UX, the UI, the frontend, or the backend.
---

# UX and backend start (Claude Code entry point)

This file only registers the skill for Claude Code (`/ux-backend-start`). The instructions live in one place, shared with every other agent.

Read [skills/UX-Backend-start/SKILL.md](../../../skills/UX-Backend-start/SKILL.md) completely and follow it step by step, from the repository root. Read each skill it delegates to before running that part. Do not copy its steps here; change them there.
