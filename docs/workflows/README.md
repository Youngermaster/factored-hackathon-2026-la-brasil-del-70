# Workflow pages

One page per customer workflow and one per shared mechanism. The four customer workflow pages share one structure, so their depth can be compared side by side: a `stateDiagram-v2`, a table mapping each state to its rules, clauses, tools, and exits, sequence diagrams for the normal, ambiguous, and escalation paths (each named after the scenario test that proves it), the confirmation and abstention matrix, and the tests.

## Customer workflows

| Workflow id | Page | Normal path | Ambiguous or unsupported path | Escalation path |
|---|---|---|---|---|
| `account_inquiry` | [account-inquiry.md](account-inquiry.md) | Balances with the as-of date | Two similar transfers: which one | A contested balance |
| `card_support` | [card-support.md](card-support.md) | A protective block with confirmation, step-up, and read-back | Two cards: which one | A replacement or unblock request |
| `dispute` | [dispute-intake.md](dispute-intake.md) | A case opened on a confirmed transaction, and case status | A charge without details | An amount above the automatic limit, a case past its SLA |
| `credit` | [credit-information.md](credit-information.md) | Catalog answers, an indicative result, and an application intake | Missing income, a demand for approval | A borderline or incomplete result sent to review |

Every page links the scenario tests in `services/api/tests/integration/workflows/`; the evaluation slices per workflow are in [results.md](../evaluation/results.md).

## Shared mechanisms

| Page | What it covers |
|---|---|
| [workflow-router.md](workflow-router.md) | One turn end to end, dispatch and switch rules, in-domain unsupported requests, the registry and the enabled set, the guarantees, and baseline B0 |
| [policy-evaluation.md](policy-evaluation.md) | Evaluation order and precedence, a decision end to end, explanations, and what each workflow binds |
| [grounding.md](grounding.md) | Bound policy lookup, which intents may use open retrieval, and the grounding verifier with its fallback |
| [human-service.md](human-service.md) | Live human exchange on the existing conversation, queued delivery, closure, and new-chat quota |
| [handoff.md](handoff.md) | How a handoff is built, the field walkthrough, and one worked example per workflow |
| [execution-records.md](execution-records.md) | Where records live, their fields, and explaining a decision without chain-of-thought |
| [data-pipeline.md](data-pipeline.md) | Source to serving, an incremental run with a late partition, and a breaking file |

Two mechanisms are documented next to their code rather than here: the evaluation harness in [docs/evaluation/README.md](../evaluation/README.md) (systems, scenario sets, graders, statistics, commands; its Mermaid flow is on that page) and the deployment in [deploy/README.md](../../deploy/README.md) with the topology in [ADR 0019](../adr/0019-single-host-compose-deployment.md). The degradation ladder and the traces of one conversation are in [docs/operations](../operations/degradation.md).

## Adding or disabling a workflow

A new workflow needs a catalog entry, a definition with its states and bindings, policy clauses, a B0 menu entry, scenarios, UI parts, and a page here with the same structure ([AGENTS.md](../../AGENTS.md) section 7 and the [application README](../../services/api/src/bank_agent/application/README.md)). A workflow is disabled without code changes through the enabled-workflows setting ([workflow-router.md](workflow-router.md#registry-and-the-enabled-set)).
