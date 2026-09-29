# Demo script outline for the pitch video

An outline, not a final script: scenes, what each proves, and the exact inputs. Every message below is from the demo guide (`/demo` in demo mode, `apps/web/src/features/demo-guide/model/scenarios.ts`) and was driven through the real API before it was listed. The narration states limits plainly: synthetic data, an indicative credit result, no lending decisions.

## Before recording

1. Start from a fresh compose volume, then `make up && make seed`: writes persist (a blocked card, an opened case, a recorded intake), and a charge can be disputed once. Re-running the seed restores card statuses but does not delete cases or intakes.
2. Run the API with `DEMO_MODE=true` (codes shown on screen) and the web app with `VITE_DEMO_MODE=true`. With `LLM_PROVIDER=fake` every answer comes from the deterministic path; say so if the model is not configured, and show "no disponible: se usó la ruta determinista" in the glass box as a feature, not a bug.
3. Use a 1440 px wide window (the glass box beside the chat) and one phone-width take for the chat.

## Scenes (about 3 minutes)

| # | Scene | Persona | Inputs | What it proves |
|---|---|---|---|---|
| 1 | The thesis | none | The sign-in page and its three lines (blue understands, yellow decides and verifies, red hands over) | The design thesis in the product's own colors |
| 2 | Balances with their as-of instant | `acc-mx-accounts` | "¿Cuál es el saldo de mis cuentas?" | Read-only answers state the data cut; the glass box shows the intent, the rules (`ACC.as_of_disclosed`), the tool call, and no model reasoning |
| 3 | A protective card block, in Portuguese | `crd-mx-two-cards` | "Perdi meu cartão, bloqueie por favor", "o primeiro", Confirmar, the code | Which card is asked, confirmation and step-up come before the write, and "Verificado" appears only after the read-back (yellow verified write in the trace) |
| 4 | A dispute that must go to a person | `dsp-mx-open-case` | "¿Cómo va mi aclaración?" | The SLA rule escalates; the customer gets a handoff reference and a time, not a transcript dump |
| 5 | Credit, honestly | `cre-ar-borderline` | "¿Soy elegible para un préstamo personal de 500 mil pesos a 12 meses?", then "Pedir revisión de una persona" | An indication with reasons, rules, uncertainty, and a review path; never approval wording, never a score. The glass box keeps the risk estimate and the eligibility decision in separate panels and says the language model received neither |
| 6 | The agent's side | `agent-demo-01` | Bandeja, filter by Crédito, open the handoff, Tomar, Resolver | Structured handoff: verified facts with sources, policy basis with clause text, open questions, the credit review with the internal estimate the customer never saw; claim and resolve are confirmed and audited |
| 7 | The evaluator's side | `evaluator-demo-01` | Registros, paste the conversation reference from scene 5 | The full record, with the internal section (risk tier, trust events, estimate values) set apart from what the customer saw |
| 8 | Results | `evaluator-demo-01` | Evaluación | Per-workflow tables before the aggregate, intervals and sample sizes, and labels (offline, simulated, projected). Until phase 14 publishes a run, the empty state explains how |
| 9 | Close | none | The About page | What each workflow does and does not do, and that the data and the credit rules are synthetic |

## Lines to avoid

- Never say "approved", "aprobado", or "aprovado" about credit, even negated in narration over the eligibility card.
- Do not claim model quality from these takes: with the fake provider the answers are deterministic templates. Evaluation numbers come only from the evaluation view (phase 14).
- Do not show document numbers or phone digits; sign in with the persona picker.
