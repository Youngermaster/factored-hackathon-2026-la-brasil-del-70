# 0011: Policy as data plus pure rule functions

- Status: accepted
- Date: 2026-09-27

## Context

The brief requires that permissions and policy are enforced outside model-generated prose, that the system defines which requests it answers, which actions need confirmation, and when it abstains or transfers, and that explanations come from sources, policy rules, and execution records. Credit adds a clearly labeled synthetic eligibility service that never approves anything. The four workflows (CLAUDE.md section 1) share authentication, privacy, and escalation rules but differ per jurisdiction (Mexico, Colombia, Argentina) in windows, SLAs, limits, and thresholds, and every customer-facing explanation must exist in Spanish and Portuguese, with English for the console.

## Considered options

1. **Rules in prompts.** Describe the policy to the language model and let it decide. Cheap to write, but decisions are not deterministic, cannot be tested at boundaries, and fail the brief's requirement that policy is enforced outside model prose.
2. **Rules hard-coded in workflow code.** Deterministic, but parameters and customer-facing text drift apart, every change is a code change, and the explanation shown to a customer is not provably the rule that ran.
3. **An external policy engine now (for example Open Policy Agent with Rego).** Mature and auditable, but it adds a service and a second language to a prototype, and its decisions still need the clause text and citations that this system shows customers.
4. **Policy as data plus pure rule functions.** Clause files (one per clause per language, front matter validated against `contracts/schemas/policy_clause.v1.json`) carry the parameters, the bound rule ids, and the customer-facing text; pure Python functions registered by id read those parameters; a pure evaluator combines rule results into a `Decision`.

## Decision

Option 4, implemented in `bank_agent/policy` over the pack in `policies/`.

- **Same source for rules and explanations.** A rule's parameters are the merged parameters of the clauses that bind it (for the customer's jurisdiction or `ALL`), and those clauses are its citations; the evaluator runs the bound rules of the clauses bound to the workflow state. What a customer reads is rendered from the same clause at the same version the rule used.
- **Pure and deterministic.** The evaluator takes the state, the action request, the session snapshot, the trust state, and the facts, and does no I/O; time windows count to the data's as-of date passed in as a fact (`POLICY_DATA_AS_OF`), never to the wall clock. Rule order is fixed (AUTH, PRV, SCOPE, ACC, CRD, DSP, CRE, ESC). Precedence: authentication failures first (deny before step-up), then refuse, escalate, deny, step-up, abstain, clarify; confirmation, then allow, only when every rule passed. Escalation therefore dominates automatic resolution.
- **Validated at load.** The loader rejects a pack with a missing language twin, differing parameters or placeholders, a placeholder that names no parameter, a content change without a version bump (`versions.lock.yaml`), an unregistered rule, a rule without its parameters in some jurisdiction, a binding to an unknown clause, or a matrix row for a workflow that does not own the action. The pack version hash is stored in every decision and execution record.
- **The synthetic eligibility service is an application of the same kernel.** It implements the `EligibilityPolicy` port by running the registered ELG rules with parameters from the ELG clauses of the product's jurisdiction and type, and maps the results to an outcome in a documented order (missing fact, then review, then a failed hard rule, then an indicative pass). It is labeled `eligibility:synthetic@<pack version>`, never computes the risk estimate, and its texts contain no approval wording (a lexicon check in three languages).
- **OPA as a future adapter.** If the rule set outgrows Python functions, an OPA adapter can implement the same `evaluate` contract with the pack as its data; the clause files, citations, and tests stay.

## Consequences

- Policy changes that only move a value or reword a clause are data changes with a version bump and a review; no workflow code changes. Adding a rule needs a function, a clause, and tests.
- Every decision is explainable from rule ids, versions, reason codes, parameters used, and clause references, with no model involved; the renderer and the golden tests pin the customer-facing text in Spanish and Portuguese.
- The pack is synthetic and plausible, not real regulation; `policies/README.md` says so, and a bilingual human review is required before the workflows use it (recorded in `docs/PROGRESS.md`).
- Clause state names in `bindings.yaml` fix the state vocabulary before the phase 09 state machines exist; a changed state is a data change caught by the bindings tests.
- The kernel has to be given every fact; the workflow engine (phase 09) owns building facts from verified records and detectors.
