# 0025: In-domain unsupported requests are abstained by the owning workflow

- Status: accepted
- Date: 2026-09-27

## Context

Session 09b requires that a transfer, a bill payment, or a due date change be abstained inside `account_inquiry` with its `ACC` clause, and that a limit increase, a restructuring, or a request for a decision now be abstained inside `credit` with its `CRE` clause. The intent set has no intent for these requests: the keyword router (and the phase 10 router, trained on the same labels) predicts `unsupported` for most of them, and the 09a out-of-scope handler answers every `unsupported` request with the generic `SCOPE` clauses from the router position. The 09a scenarios also require that a limit increase is abstained with `SCOPE-ALL-2` and the decision naming `SCOPE.supported_intent`.

## Considered options

1. **Route these requests to a workflow intent** (a transfer to `payment_status`, a limit increase to `credit_product_info`) and let the workflow abstain. It bends the intent labels: phase 10 would learn that "make a transfer" is a payment-status question, and evaluation would count misroutes as correct.
2. **Add new intents** (`account_action_request`, `credit_action_request`). The catalog, the contracts (`Intent` is an enum in four schemas), the router labels, and the labeling protocol all change for requests that always end in the same abstention.
3. **Let a definition recognize its own unsupported requests.** `WorkflowDefinition.unsupported` returns an `UnsupportedRequest` (a code, the clause ids, a template). Before the generic out-of-scope answer the engine asks the current workflow, then the other enabled ones; the owning workflow abstains with its clause and `SCOPE-ALL-2`. The workflow's UNDERSTAND uses the same recognizer when the router sent the request to it directly.

## Decision

Option 3 (`application/engine/flow.py`, `in_domain_unsupported`; recognizers in `workflows/account_inquiry/unsupported.py` and `workflows/credit/unsupported.py`). The kernel still sees intent `unsupported`, so the decision names `SCOPE.supported_intent`; the reply cites the workflow clause and `SCOPE-ALL-2` and offers a human; the record carries `out_of_scope` and `unsupported_<code>`. Outside a pending step the conversation moves to the owning workflow's ABSTAINED state (a switch when a workflow was active); mid-flow the pending step is kept.

## Consequences

- The intent labels stay honest, and no contract changes.
- The recognizers are closed, deterministic lexicons in es and pt; a paraphrase they miss falls back to the generic out-of-scope answer, which is still a clause-backed abstention with a human offered.
- A cut workflow (not in `WORKFLOW_ENABLED`) recognizes nothing, so its requests get the generic answer, as the cut rule requires.
