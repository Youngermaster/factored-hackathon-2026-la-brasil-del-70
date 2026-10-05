# Limitations

What this system cannot claim, stated plainly. The brief asks for honesty about capacity limits, data limitations, language coverage, deployment work, and remaining risks; each section links to the evidence. Future work with its owner is in [docs/BACKLOG.md](docs/BACKLOG.md); open human reviews are in the "Pending human actions" list of [docs/PROGRESS.md](docs/PROGRESS.md).

## Scope: four workflows against a depth-over-breadth brief

- The brief says more workflows earn no bonus. The team built four anyway (human decision, 2026-09-26; [ADR 0020](docs/adr/0020-four-workflows-and-the-workflow-registry.md)). The scoring risk is real: four shallow flows would score worse than one deep one.
- The mitigation: every workflow meets the same bar (policy clauses, bound clauses per state, an explicit state machine, verified actions, a structured handoff, es and pt, a workflow page), the engine, policy kernel, grounding verifier, and evaluation harness carry the depth once, and every workflow is evaluated separately. No workflow was cut back under the CLAUDE.md section 1 rule.
- The per-workflow samples are small: 76 test cases per workflow (47 es, 29 pt). No language, dialect, or segment difference is established, and the pt cells are under 30 cases ([results](docs/evaluation/results.md)).
- Card support does not beat the menu baseline: on the hosted test run P resolves 48 of 76 safely against B0's 47 of 76 (a tie; the local 14b run had 40 against 43). Escalation prompt v2 cut P's unnecessary card transfers from 11 to 5 of 59, and 2 Portuguese stolen-card requests are still read as distress ([results](docs/evaluation/results.md#card_support-against-the-local-run)).
- `card_support` has no demand evidence under the strict reason mapping, and `dispute` has the weakest data support: no complaint links to a transaction ([prioritization](docs/decisions/workflow-prioritization.md), "Breadth risk").

## Credit

- The eligibility rules (`ELG.*`), their thresholds, and the credit catalog are team-authored and synthetic, labeled so wherever they appear. They are not a bank's policy, and their review by people is pending (pending actions 17 and 34 in PROGRESS).
- The risk estimate is cross-sectional: the delivery has one snapshot, so the label is delinquency at that snapshot, not a forward-looking default. Its only real signal is the number of credit products; credit score, income, tenure, and utilization show no association with the label (univariate ROC AUC 0.495 to 0.502; [model card](docs/models/risk-estimator.md), [ADR 0030](docs/adr/0030-credit-risk-estimator.md)). The API serves the score-band baseline (`score_band@1`) by default.
- None of it is a lending model. There is no approved outcome, no lending decision, and no movement of money; the language model never sees the risk estimate or the credit profile.

## Data

- The organizer data is synthetic, with generator artifacts documented in the [data card](docs/data/data-card.md): for example 149,995 of 150,000 customers reference a branch that does not exist, all 44,570 complaint product references name another customer's product, and some cards marked active carry expiry dates in the past.
- There is no Portuguese source text: every customer is in Mexico, Colombia, or Argentina, so Portuguese conversations are played by those customers in their currencies.
- Transcripts come from phone calls and hold 42 distinct customer texts across 147,292 transcripts, so they carry no usable intent signal; routing learns from team-written, team-labeled utterances.
- No complaint links to a transaction, so the dispute workflow confirms the transaction with the customer and the resolver's labels are built by construction ([resolver card](docs/models/resolver.md)).
- The committed sample supports 12 of the 16 customer demo personas; the other four exist only after a seed from the full delivery ([personas](docs/demo/personas.md)).
- Cost figures from the historical data are projections from unverified team assumptions (`data_platform/analysis/cost_assumptions.yaml`, pending action 12).

## Language coverage and review status

- Customer copy exists in Spanish and Portuguese; the agent and evaluator console in English and Spanish. The Portuguese copy, the pt router seeds, and the pt evaluation phrasings have had no native review (pending actions 28, 38, 41).
- The policy clauses in es, pt, and en wait for a bilingual review per workflow (pending action 16).
- The language detector is an in-house lexical detector (es 88.2% correct, pt 87.1% on the router corpus); the larger lingua detector waits for a size decision (pending action 22).

## Evaluation

- The published run (`test-hosted`) uses one hosted model, `azure/gpt-4.1-mini`, for every model role: P's understanding, the naive agent B1, and the simulated customer. The simulated customer therefore runs on the same model as the systems it tests. The numbers are a simulation on a synthetic world, not a production measurement. The run is at commit `2ddabb0`, before the final-day QA fixes, which are not measured. The previous run on the local `qwen2.5:7b-instruct` is archived in [docs/evaluation/runs/test-local](docs/evaluation/runs/test-local/results.md).
- The 332 test scenarios and their labels are team-written from the policy documents; none is human-reviewed yet (pending action 41).
- The graders are lexical. On the hosted run P's single graded unsafe outcome is a consented, confirmed, step-up-verified second write (the optional protective block) that the scenario did not expect, and B0's three are a dispute amount read as a balance; the counts are reported as graded. No simulated-customer turn carried a redaction placeholder (the 14b run had 22 of 258).
- The judge was not rerun on the hosted run, so no tone or clarity rating is published for it; the 14b judge (local model) has no human agreement yet (pending action 40).
- Repeated runs cover a 48-scenario subset, not the full split. Latency is in process, one model call at a time, with two evaluation processes sharing one Azure deployment; it is not a production latency. Azure's jailbreak filter rejected a few calls in direct prompt-injection scenarios; those cases are kept as played.
- The retrieval relevance judgments and the router validation sample are unlabeled by humans, so those results are provisional (pending actions 19 and 27).
- The cost figures are provider-reported tokens priced at the Azure list price (the repository entry awaits a person's confirmation); no invoice was reconciled.

## Capacity

Measured on one laptop without a model ([capacity](docs/operations/capacity.md)): on the production stack with two workers capped at 1.5 CPUs, 27.4 turns per second at 50 simulated customers with p95 250 ms and no errors; the ceiling is the API's CPU allowance, then Jaeger's memory. With a model, the model call dominates latency (P's p50 per turn is 2.3 s on the local model). The load test has not been repeated on a cloud host.

## Deployment work remaining

The event deployment is one VM with Docker Compose ([ADR 0019](docs/adr/0019-single-host-compose-deployment.md), [deploy guide](deploy/README.md)). A real bank deployment still needs:

- managed PostgreSQL with point-in-time recovery, and a container service with a load balancer and more than one host (high availability);
- key management beyond the event setup: the secrets live in Azure Key Vault, read by the VM's managed identity ([ADR 0037](docs/adr/0037-cloud-secret-management-with-azure-key-vault.md)), but rotation schedules and access reviews are manual, and the model is reached with API keys rather than a managed identity;
- a real identity provider and a real one-time-code channel instead of the demo sender that shows codes on screen ([demo mode](docs/security/demo-mode.md));
- for the Azure OpenAI deployment the demo uses: a provider-side spending limit (today the application's own budget caps and token limits are the only spending bounds) and a recorded review of its data controls (pending action 45);
- a compliance review: data retention periods, consumer-credit and dispute regulation per country, and accessibility;
- freshness alerts once there is a scheduled data load, and a shared degradation level across workers.

The event host is one Azure VM (`Standard_B2as_v2`, westus2) at <https://la-brasil-del-70.westus2.cloudapp.azure.com>, released from `main` by the deploy workflow ([ADR 0038](docs/adr/0038-continuous-deployment-to-azure-with-github-actions.md)); it stays up until 2026-10-16.

## Remaining risks

- On the published run, untrusted merchant text reached a dispute confirmation summary unmasked (three echoed injections; no other customer's data was read). Masking of instruction-like record text was added afterwards (phase 14c follow-up, with regression tests on the memory and PostgreSQL backends) and has not been re-measured by an evaluation run.
- The grounding verifier is lexical and closed: numbers written as words and paraphrased claims pass unnoticed; the template fallback covers what it misses ([grounding](docs/workflows/grounding.md)).
- The in-domain unsupported recognizers and the keyword router are closed lexicons; paraphrases they miss fall back to the generic answer or a clarifying question.
- Zero observed failures in a small test set does not establish zero risk: an unsafe rate of 0/76 still allows up to 3.9% at 95% confidence.
- The public demo shows one-time codes by design, bounded by synthetic data, rate limits, budget caps, retention, and a take-down date ([demo mode](docs/security/demo-mode.md)).

## Live human service

- The channel requires an authenticated person to claim the handoff. When nobody takes it, the customer stays truthfully queued; there is no simulated reply or staffing guarantee.
- Delivery uses two-second polling and persisted sequence cursors. A joined state means the handoff was claimed; it is not a live presence heartbeat. Transport errors show a separate reconnect notice.
- The frozen assistant evaluation predates this capability. Repository contracts, HTTP exchanges, web integration checks, and non-superuser production-role checks verify it; published assistant success rates are not live-service measurements. See [the channel guide](docs/workflows/human-service.md).
