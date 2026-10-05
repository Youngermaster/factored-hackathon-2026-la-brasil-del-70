# Video monologue

The spoken script of the video pitch, split across the four members of La Brasil del 70. It is the same text as the narration in [slides/script.md](../../slides/script.md), in the same order; `pnpm check:content` (from `slides/`) fails when the two differ by one word or one speaker, and when the word-count table below is wrong. What is on screen during each line, and the exact clicks, is in the [video plan](video-plan.md).

The video has a hard limit of 3:00, demo footage included. The cut targets 2:50. At 150 words per minute the 376 spoken words take about 2:30, which leaves about 20 seconds for typing, loading, and the pauses after each click.

## Who says what, and why

| Speaker | Words | Seconds at 150 wpm | Segments | Why this person |
|---|---|---|---|---|
| Juan Young | 119 | 48 | guardrail, backend trace, architecture | Technical lead: built the core architecture, the agent integration, and the safety layers the guardrail shows |
| Miguel Correa | 83 | 33 | hook close line, Portuguese handoff, close | Project manager: owns the problem framing, the product story, and the pitch |
| David Fonseca | 85 | 34 | card block, the learned-model decision | Presents the demo flow and the machine learning trade-off |
| Julián Valencia | 89 | 36 | hook data line, Grafana, evidence | Data engineering and the evaluation evidence: the pipeline, the analytics, the results |

To swap a part, move the `**Name:**` tag here and the matching `[Name]` tag in `slides/script.md`, then run `pnpm check:content`: it prints the new counts and fails until this table matches them. Keep each person's lines in one or two blocks; a voice change every few seconds is hard to follow.

## The script

Words in square brackets are cues, not speech. Times are the video timeline in the [video plan](video-plan.md).

### 0:00 to 0:14, hook (slide 1)

**Julián Valencia:** [arrive] A synthetic Latin American bank: twenty-three and a half million rows. [click 1] [click 2] Disputes hurt most: only forty-four percent are resolved at first contact.

**Miguel Correa:** We are La Brasil del 70, and this is Bank Agent.

### 0:14 to 0:34, guardrail (live)

**Juan Young:** This is the customer chat. On the right, the glass box records every turn. Who is better, Cristiano or Messi? It declines, lists what it can help with, and cites the scope clause. No tool ran. Another customer's credit card? Refused under the privacy clause, and the number is never repeated.

### 0:34 to 1:08, a protective card block in Spanish (live)

**David Fonseca:** Now a real task, in Spanish: I lost my card, block it. The model only understands. The glass box shows the intent, then the rules that decided, each tied to a policy clause. Two cards, so it asks which one instead of guessing. Before writing, it asks for confirmation and a fresh one-time code. It says blocked only after reading the card back.

### 1:08 to 1:28, Portuguese escalation and the agent console (live)

**Miguel Correa:** The same engine, in Portuguese. This customer threatens to go to the central bank, so a person takes over, with verified facts and open questions, not the transcript. In the agent console, an agent claims the case and answers in the same conversation.

### 1:28 to 1:46, the backend (live)

**Juan Young:** Behind each reply is a full execution record, and one OpenTelemetry trace from the HTTP request through the router, the policy check, the tool call and its SQL.

**Julián Valencia:** Grafana turns the same telemetry into live operations: turns by workflow, outcomes, escalations, safety interventions and latency.

### 1:46 to 2:12, architecture (slide 3)

**Juan Young:** [arrive] FastAPI with a hexagonal core, React, and PostgreSQL with row-level security. [click 1] It runs on one VM: Docker Compose behind Caddy, with the observability stack beside it. [click 2] Model calls pass one gateway to Azure OpenAI, so the provider is a setting.

**David Fonseca:** [click 3] Our learned router, resolver and risk estimator beat their baselines offline, but not end to end, so the baselines stay the default.

### 2:12 to 2:36, evidence (slide 5)

**Julián Valencia:** [arrive] Three hundred and four held-out cases, three systems, simulated on a small local model. [click 1] Per workflow first: card support is not ahead of the menu and rules bot yet. [click 2] In aggregate, fifty-eight percent safe automated resolution, against forty-two and thirteen. [click 3] Eight unsafe outcomes, against ninety for the naive LLM agent.

### 2:36 to 2:50, close (slide 6)

**Miguel Correa:** [arrive] When something fails, it steps down, and writes never fail open. [click 2] We cannot claim real data or a hosted-model evaluation yet. [click 4] The model understands. Code decides. Evidence proves it.

## Lines to keep exact

- Credit: never say "approved", "aprobado", or "aprovado", even negated. The video does not play a credit case.
- Numbers: every number spoken is in `slides/data/metrics.yml`; the evidence numbers are a simulation on the local model `qwen2.5:7b-instruct`, and the line says so ("simulated on a small local model").
- The deployed demo calls Azure OpenAI `azure/gpt-4.1-mini` (fallback `azure/gpt-4o`) to extract details and detect escalation signals; the published evaluation did not measure it, so its numbers come from the local `qwen2.5:7b-instruct`. Do not present the live replies as the evaluated system's quality.
- "Cristiano or Messi" is spoken in English over the Spanish message on screen ("¿Quién es mejor CR7 o Messi?").

## Rehearsal checklist

- [ ] Each speaker reads their lines aloud against a timer twice; the whole read stays under 2:40 without footage.
- [ ] Read from this page, not from memory: the check keeps it identical to `slides/script.md`.
- [ ] Every speaker records in the same room setup (see [slides/VIDEO.md](../../slides/VIDEO.md), "Audio"), 2 seconds of silence first, at 48 kHz.
- [ ] Speak each line only after the click it follows has landed; a line never runs over the next click.
- [ ] Juan rehearses the guardrail segment against the live chat once, so the two messages are typed before the line that describes them.
- [ ] David rehearses the card block end to end on a fresh seed (it writes, so it can run once per seed).
- [ ] Miguel confirms the agent console shows the Portuguese handoff before recording the voice line for it.
- [ ] Julián checks the Grafana panels named in the plan show non-zero values before the take.
- [ ] Final cut measured at 2:50 or less; 3:00 is a hard limit, not a target.
- [ ] Captions burned in or attached, from this text.
