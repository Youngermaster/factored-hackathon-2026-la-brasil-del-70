# bank_agent.policy

The deterministic policy kernel: it loads the synthetic policy pack (`policies/`), evaluates pure rules against facts it is given, explains decisions from clause text, and runs the synthetic eligibility service. It performs no I/O, reads no clock, and never calls a language model. Decisions follow [ADR 0011](../../../../../docs/adr/0011-policy-as-data-and-pure-rule-functions.md); the evaluation order is drawn in [`docs/workflows/policy-evaluation.md`](../../../../../docs/workflows/policy-evaluation.md).

## Responsibility

- Parse and validate the pack from text (`loader/`): clause schema, language parity, placeholders, the version lock, bindings, the action matrix, rule parameters, messages, and the credit catalog against the pack.
- Evaluate a workflow state (`evaluator.py`): run the bound rules in a fixed order and combine their effects into a `Decision` that names every rule id, rule version, and clause reference.
- Explain (`explain.py`): render clause bodies with their parameters in the session language and locale, with `clause_id@version` citations.
- Assess credit eligibility (`eligibility/`): the `EligibilityPolicy` port over the ELG rules, and its renderer.

## Who may import it

`application`, `adapters`, `api`, and `bootstrap`. The policy package imports only `ports` and `domain` (plus PyYAML for parsing text), and the pure-core contract forbids `fastapi`, `sqlalchemy`, `httpx`, `boto3`, and `litellm`.

## Public interfaces

| Module | Interface |
|---|---|
| `pack.py` | `PolicyPack` (implements `PolicyRepository`), `Bindings`, `StateBinding`, `PackInfo` |
| `loader/` | `load_pack(files)`, `pack_version(files)`; `loader.catalog.parse_catalog`, `check_catalog_against_pack`; `loader.lock.render_lock` |
| `facts.py` | `EvaluationRequest`, `PolicyFacts` and its parts (`AccountFacts`, `CardFacts`, `DisputeFacts`, `CreditFacts`, `EscalationSignals`, `PrivacySignals`) |
| `evaluator.py` | `evaluate(request, pack) -> Decision`, `rules_for`, `combine` |
| `rules/` | `CONVERSATION_RULES`, `ELIGIBILITY_RULES` (registries), `RuleContext`, `EligibilityContext` |
| `explain.py` | `explain`, `explain_decision`, `render_body`, `format_money`, `RenderedExplanation` |
| `eligibility/` | `SyntheticEligibilityService`, `map_outcome`, `render_eligibility` |
| `lexicon.py` | `approval_terms(text)` |
| `catalog_doc.py` | `render_catalog` (the generated `docs/policy/catalog.md`) |

The filesystem adapters (`adapters/policy/`) read `policies/` and call the loader; `bootstrap/policy.py` builds `PolicyServices` (pack, catalog, eligibility service, tool parameters, data as-of date) for the container.

## How to extend

- **A rule.** Write a pure function in the matching `rules/` module and register it with `@RULES.rule("FAM.name", version=1, reasons=(...), params={...}, missing_facts=(...))`. Declare every reason code it can return and every parameter it reads; the loader fails a pack that does not bind the rule in every jurisdiction or lacks a parameter. Then bind a clause to it (`bound_rules`) and add unit tests with boundary values and a missing-fact case.
- **A clause or a parameter value.** Edit the pack files as described in [`policies/README.md`](../../../../../policies/README.md); no code changes.
- **A fact.** Add an optional field to the right model in `facts.py` (record facts optional, detector signals defaulting to "not detected"), and make the rule fail safely when it is missing.
- **An external engine (for example OPA).** Implement the same `evaluate` contract behind a port and keep the pack as its data; ADR 0011 records this as a future option.

## How to test

```bash
uv run pytest services/api/tests/unit/policy -q          # rules, evaluator, properties, eligibility, loader parts
uv run pytest services/api/tests/integration/policy -q   # the real pack, the situation table, golden texts
uv run pytest services/api/tests/contracts -q -k "catalog or eligibility"
```

Unit tests use the in-memory fixture pack in `services/api/tests/bank_agent_policy.py`; integration tests read the repository pack.
