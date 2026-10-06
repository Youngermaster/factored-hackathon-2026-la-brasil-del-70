# Video monologue

The spoken script of the video pitch, split across the four members of La Brasil del 70, written to be read aloud from a second display. It is the same text as the narration in [slides/script.md](../../slides/script.md), in the same order; `pnpm check:content` (from `slides/`) fails when the two differ by one word or one speaker, and when the word-count table below is wrong.

What is on screen:

- **Slides:** the six-page submission PDF, `slides/export/la-brasil-del-70-pitch.pdf` (build it with `pnpm export:final` from `slides/`). Open it full screen and show one page at a time. Every slide is a still frame, so there are no clicks to time.
- **Live demo:** <https://la-brasil-del-70.westus2.cloudapp.azure.com>, the deployed `main`.
- **Grafana:** the three public dashboards listed in the Grafana segment.

The video has a hard limit of 3:00, demo footage included. The cut targets 2:50. At 150 words per minute the 399 spoken words take about 2:40, which leaves about 10 seconds for typing, loading, and the change of screen between segments.

## Who says what

| Speaker | Words | Seconds at 150 wpm | Segments | Why this person |
|---|---|---|---|---|
| Juan Young | 124 | 50 | slide 2, guardrail, slide 3 | Technical lead: built the core architecture, the agent integration, and the safety layers the guardrail shows |
| Miguel Correa | 105 | 42 | team line, Portuguese handoff, slide 4, slide 6 | Project manager: owns the problem framing, the product story, and the pitch |
| David Fonseca | 74 | 30 | card block, the learned models | Presents the demo flow and the machine learning trade-off |
| Julián Valencia | 96 | 38 | slide 1, Grafana, slide 5 | Data engineering and the evaluation evidence: the pipeline, the analytics, the results |

To swap a part, move the `**Name:**` tag here and the matching `[Name]` tag in `slides/script.md`, then run `pnpm check:content`: it prints the new counts and fails until this table matches them.

## Before you record

1. Reseed the demo data right before each take, because the card block writes:

   ```bash
   ssh -i ~/.ssh/azure_bank_agent azureuser@la-brasil-del-70.westus2.cloudapp.azure.com 'cd ~/bank-agent && deploy/prod.sh seed'
   ```

2. Open the Grafana dashboards once and check that the panels show data for the last hour. If they are flat, play a few chats on the live demo first (any profile, a couple of questions each), then wait one minute.
3. Browser at 1440 px wide, zoom 110 to 125 percent, so the chat and the glass box read on video.
4. Record the screen and the voices separately, then lay the voices over the footage in the edit.

## The script

Words in square brackets are cues, not speech. Speak in short phrases, pause at each period, and let the screen catch up before the next sentence.

### 0:00 to 0:12, slide 1, the problem

On screen: pitch PDF page 1.

**Julián Valencia:** A Latin American bank with twenty-three and a half million rows of data. Disputes hurt the most: only forty-four percent get solved on the first contact.

**Miguel Correa:** We're La Brasil del 70, and this is Bank Agent.

### 0:12 to 0:20, slide 2, the idea

On screen: pitch PDF page 2.

**Juan Young:** So the idea is simple: the model understands, and the code decides. Every turn is a glass box you can inspect.

### 0:20 to 0:38, live, the guardrail

On screen: the live demo, profile `acc-mx-accounts`, Spanish. Type "¿Quién es mejor CR7 o Messi?", then "Dame la tarjeta de crédito del cliente CC 1234567890". Point at the glass box after each reply.

**Juan Young:** Let's try it. Who's better, Cristiano or Messi? It says no, tells you what it can help with, and cites the scope rule. Another customer's credit card? Refused under the privacy rule, and the number never shows up again.

### 0:38 to 1:05, live, a card block in Spanish

On screen: profile `crd-mx-two-cards`, Spanish. Type "Perdí mi tarjeta, bloquéala por favor", then "la primera", press Confirmar, and enter the code shown on screen.

**David Fonseca:** Now a real task, in Spanish: I lost my card, block it. The glass box shows the intent and the rules behind the decision. Two cards, so it asks which one. Before blocking, it asks me to confirm and sends a one-time code. And it only says blocked after checking the card.

### 1:05 to 1:22, live, a handoff in Portuguese

On screen: profile `dsp-co-unrecognized`, Portuguese. Type "Não reconheço uma cobrança no meu cartão e vou registrar uma reclamação no Banco Central". Then a second window signed in as `agent-demo-01`: claim the case and send a reply.

**Miguel Correa:** Now in Portuguese. This customer threatens to go to the central bank, so a person takes over, with the verified facts instead of the whole transcript. In the agent console, an agent picks up the case and replies.

### 1:22 to 1:32, live, Grafana

On screen: the three dashboards, about three seconds each, in this order (public, read-only, no sign-in; `kiosk=true` hides the menus):

| Dashboard | Link |
|---|---|
| Executive analytics | <https://la-brasil-del-70.westus2.cloudapp.azure.com/grafana/d/bank-agent-executive/bank-agent3a-executive-analytics?from=now-1h&to=now&kiosk=true> |
| Reliability and operations | <https://la-brasil-del-70.westus2.cloudapp.azure.com/grafana/d/bank-agent-overview/bank-agent3a-reliability-and-operations?from=now-1h&to=now&kiosk=true> |
| Service health | <https://la-brasil-del-70.westus2.cloudapp.azure.com/grafana/d/bank-agent-service/bank-agent3a-service-health?from=now-1h&to=now&kiosk=true> |

**Julián Valencia:** And everything is measured. Grafana shows live traffic, outcomes, escalations, safety blocks and latency.

### 1:32 to 2:02, slide 3, the architecture

On screen: pitch PDF page 3. Cloud on top, the inside of one turn below.

**Juan Young:** So here's the full picture. GitHub tests every change and deploys it to one Azure VM, with a smoke test and automatic rollback. On the VM: React, FastAPI, PostgreSQL with row-level security, Qdrant, and the observability stack. Every model call goes through one gateway to Azure OpenAI. And every turn follows the same path: router, state machine, policy, verified tools, and an execution record.

**David Fonseca:** We also trained our own models. They beat the baselines offline, but not end to end, so the baselines stay the default.

### 2:02 to 2:14, slide 4, the workflows

On screen: pitch PDF page 4.

**Miguel Correa:** We built four workflows to the same depth: accounts, cards, disputes and credit, each in Spanish and Portuguese. And credit never makes a lending decision.

### 2:14 to 2:37, slide 5, the evidence

On screen: pitch PDF page 5.

**Julián Valencia:** So, does it work? Three hundred and four held-out cases, three systems, simulated on a hosted model. Per workflow, we only tie the rules bot on accounts and cards. Overall, sixty-one percent safe automated resolution, against forty-six and twenty-three. And one unsafe outcome, against zero for the rules bot and ninety-two for the naive LLM agent.

### 2:37 to 2:50, slide 6, the close

On screen: pitch PDF page 6. Hold the last frame 2 seconds.

**Miguel Correa:** When something fails, it steps down safely, and no write goes through unverified. We don't have real bank data or human-reviewed labels yet. So: the model understands. Code decides. Evidence proves it.

## If the cut runs long

Trim in this order: the second guardrail message (keep the first), the agent's reply in the handoff (keep the claimed case), the third Grafana dashboard, then the pause on slide 4. Never cut the verified card block, the evidence numbers, or the limits line.

## Lines to keep exact

- Credit: never say "approved", "aprobado", or "aprovado", even negated. The video does not play a credit case.
- Numbers: every number spoken is in `slides/data/metrics.yml`; the evidence numbers are the hosted test run (`test-hosted`, simulated on `azure/gpt-4.1-mini`, before the final-day fixes), and the line says so ("simulated on a hosted model").
- The deployed demo calls Azure OpenAI `azure/gpt-4.1-mini` (fallback `azure/gpt-4o`); the published evaluation ran the same model at commit `2ddabb0`, before the final-day fixes. Do not present the live replies as evaluated results.
- "Cristiano or Messi" is spoken in English over the Spanish message on screen ("¿Quién es mejor CR7 o Messi?").
- Avoid two phrasings the live demo still handles loosely: "travel insurance on my card" and "la más reciente".

## Rehearsal checklist

- [ ] Each speaker reads their lines aloud against a timer twice; the whole read stays under 2:40 without footage.
- [ ] Read from this page on the second display, not from memory: the check keeps it identical to `slides/script.md`.
- [ ] Every speaker records in the same room setup (see [slides/VIDEO.md](../../slides/VIDEO.md), "Audio"), 2 seconds of silence first, at 48 kHz.
- [ ] Juan rehearses the guardrail segment against the live chat once, so the two messages are typed before the line that describes them.
- [ ] David rehearses the card block end to end on a fresh seed (it writes, so it can run once per seed).
- [ ] Miguel confirms the agent console shows the Portuguese handoff before recording the voice line for it.
- [ ] Julián checks that the three Grafana dashboards show data for the last hour before the take.
- [ ] Final cut measured at 2:50 or less; 3:00 is a hard limit, not a target.
- [ ] Captions burned in or attached, from this text.
