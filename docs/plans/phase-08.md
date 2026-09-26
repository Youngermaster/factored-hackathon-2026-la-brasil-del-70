# Phase 08 plan: LLM gateway, composable reliability, and the prompt registry

Status: no plan mode required for this phase (orchestrator instruction, 2026-09-26). Written against commit `4a4af79`. Phases 03 to 07 have not run (no `.env` yet); this phase depends only on the phase 02 and 02b ports and fakes.

Human decision recorded for this phase: **the LLM provider is undecided.** The LiteLLM adapter is built behind the port, but nothing calls a live provider, in tests or otherwise, and no cassette is recorded against a live key. Cassettes that the prompt expects to be recorded are hand-authored fixtures, labeled `provenance: hand_authored_fixture`; recording real ones is a pending human action, not a blocker.

## Read-only findings

| Finding | Consequence |
|---|---|
| `LLMClient` already has the task 1 surface (`generate_structured`, `generate_text`, `language`, `max_output_tokens`, `temperature`, plus `call_context`), and the six typed errors exist in `domain/errors.py` | No port change. One subtype is added: `LlmProviderRejectedError(LlmProviderError)`, not retryable, for 4xx provider rejections and for "no provider configured"; callers that handle `provider_error` handle it unchanged |
| `FakeLLM` lives in `bank_agent.testing`, which production layers may not import; `input_hash` and `canonical_variables` live there too | Canonicalization moves to `domain/intelligence.py` (pure, re-exported from `testing.fake_llm`), so the cassette adapter can use it. `FakeLLM` stays a test double: the composition root accepts an injected base client (tests and the evaluation harness pass `FakeLLM` or a cassette client). With `LLM_PROVIDER=fake` and no injected client, the root uses `UnconfiguredLLMClient`, which raises `LlmProviderRejectedError` on every call, so workflows run on their deterministic fallbacks |
| `PromptTemplate` has no owner or changelog and is used nowhere else | It gains `owner`, `changelog`, and `description` on variables (not a published contract) |
| `LlmCallContext` carries lineage, conversation, and turn ids only | It gains `sensitive_terms` (for example the session's first name, marked `Pii("name")`), so the redaction decorator can mask names it knows about in addition to the name heuristics |
| `bootstrap/logging.py` already scrubs emails, CPF, CNPJ, CURP, dotted numbers, phones, and digit runs | Its policy is "scrub everything"; prompts must keep amounts such as `$1.500.000`. The LLM redactor is a separate, currency-aware module in `adapters/llm/` with its own test table |
| The `Telemetry` port is the only tracing facade (OpenTelemetry arrives in phase 15) | `TracingDecorator` writes GenAI semantic convention attributes (pinned to semantic conventions 1.37.0) through the port; phase 15's adapter sets the schema URL |
| `pyyaml` 6.0.3 is already in `uv.lock` (through bandit) | It becomes a direct runtime dependency (MIT) for prompt front matter and the price table; `types-pyyaml` joins the dev group |
| `litellm` 1.102.1 (MIT) measured in a scratch venv: 84 MB for the package, 170 MB with its dependencies (boto3, openai, tokenizers, huggingface-hub, and more) | Above the 50 MB rule, and it handles provider keys. It goes into an optional `litellm` extra of `bank-agent`, pinned exactly, imported lazily, never installed by `make setup`. Human review item |

## Files to create or change

| Path | Change |
|---|---|
| `services/api/src/bank_agent/domain/intelligence.py` | `canonical_variables`, `input_hash`, `LlmCallContext.sensitive_terms`, `PromptTemplate` owner and changelog |
| `services/api/src/bank_agent/domain/errors.py` | `LlmProviderRejectedError` |
| `services/api/src/bank_agent/domain/llm_outputs.py` | Output models: `DisputeSlotExtraction`, `AccountInquirySlotExtraction`, `CardSupportSlotExtraction`, `CreditSlotExtraction`, `IntentClassification` (labels = every `Intent` plus `out_of_scope`), `EscalationSignals`, `HandoffSummaryDraft`; `OUTPUT_MODELS` catalog; `FORBIDDEN_PROMPT_VARIABLES` |
| `services/api/src/bank_agent/testing/fake_llm.py` | Re-export canonicalization from the domain |
| `services/api/src/bank_agent/adapters/prompts/file_registry.py` | `FilePromptRegistry`: loads `bank_agent/prompts/<id>/<version>.md`, validates front matter, placeholders, output models, forbidden variables; renders system and user messages with data delimiters |
| `services/api/src/bank_agent/prompts/<id>/1.md` | The eight prompts of task 6 |
| `services/api/src/bank_agent/adapters/llm/` | `request.py` (call value object, decorator base), `client.py` (`PromptedLLMClient`: rendering, language directive, structured output with one repair), `litellm_client.py` (`LiteLLMCompletion`, `LiteLLMClient`), `unconfigured.py`, `cassette.py`, `redaction.py`, `prices.py`, `budget.py`, and one module per decorator |
| `services/api/config/llm_prices.yaml` | Dated candidate prices with `source_url` and `verified: false` |
| `services/api/src/bank_agent/bootstrap/settings.py`, `container.py` | New `LLM_*` settings; the stack built from settings in the documented order |
| `.env.example` | The new optional `LLM_*` names |
| `evals/cassettes/` | Hand-authored fixture cassettes and a README |
| `services/api/pyproject.toml`, root `pyproject.toml`, `uv.lock` | `pyyaml`, the `litellm` extra, `types-pyyaml`, a mypy override for `litellm` |
| Docs | `docs/architecture/llm-gateway.md`, `docs/security/prompt-injection.md`, ADR 0013, `prompts/README.md`, adapters, testing, bootstrap READMEs, `ports-and-adapters.md`, `docs/README.md`, BACKLOG, PROGRESS |

## Decorator order

Outermost first: redaction, budget guard, tracing, cost accounting, fallback, then per provider: circuit breaker, bounded retry, timeout, provider. This keeps the prompt's order (redaction, budget, tracing, circuit breaker, retry, timeout, provider) and places the two decorators it does not order: cost accounting sits inside tracing and budget so both see the cost of the call, and fallback sits above the per-provider reliability stacks so each provider has its own breaker. Without a fallback model there is no fallback decorator. A test walks the chain.

## Budget rules

- Per session (lineage) token cap, per conversation cost cap, daily cost cap (UTC day from the `Clock`).
- Before a call the guard reserves the worst case of the output (`max_output_tokens` at the highest effective output price among the configured models) and rejects when the reservation would cross a cap.
- After a call it records the actual usage and cost. After `invalid_output` or `timeout` it charges the reservation, because the provider may have billed tokens the error does not report.
- Prices: a verified entry is used as is; an unverified entry is multiplied by `unverified_price_multiplier` from the YAML file; a model missing from the table is charged at the highest known input and output prices times the multiplier. No price is written in code.
- The ledger is in memory per process (limitation, BACKLOG for phase 15).

## Tests to add

- Unit, per decorator: retry bounds and backoff with a fake sleeper and seeded jitter; circuit breaker transitions with `FixedClock`; fallback order and typed failure; budget exceeded for each cap, reservation charging; redaction table (es, pt, CC, CURP, DNI, CPF, phones, emails, card numbers, digit runs, names) with false-positive checks (amounts, dates, last four digits); tracing attributes; cost math for verified, unverified, and unknown models; timeout.
- Registry: loads every prompt; unknown prompt and version; missing, unknown, and mistyped variables; delimiters and escaping; a test that fails if any prompt declares a variable carrying a risk estimate, a credit profile field, or an internal flag.
- Structured output: parse, repair, failure after repair, through `PromptedLLMClient` with a scripted completion.
- LiteLLM adapter: request shape, response parsing, error mapping by status code, with an injected completion function (no network, litellm not installed).
- Cassettes: record then replay is identical; missing cassette in replay raises; redaction before writing; key stability; every fixture cassette's key matches its content; per workflow, es and pt, normal, ambiguous, and out-of-scope cases for every extraction prompt; a Brazilian Portuguese check over the pt `phrase_response` cassettes.
- Composition: order test; integration test that builds the full stack from settings with `FakeLLM` and exercises success, retry, fallback, budget, and redaction.

## Risks

| Risk | Mitigation |
|---|---|
| Hand-authored cassettes could be mistaken for real model behavior | `provenance: hand_authored_fixture`, a model id of `fixture/hand-authored`, a README, and a PROGRESS pending action |
| Redaction false positives remove amounts the workflows need | Currency-aware rules and a false-positive table |
| litellm size and supply chain exposure | Optional extra, exact pin, lazy import, local cost map, no callbacks; human review |
| The in-memory budget ledger does not share state across processes | Documented limitation, BACKLOG |

## Open questions (none blocks correctness)

1. Which provider and models? Decided by evaluation in phase 14 after the human chooses a provider; the price table lists candidates with `verified: false`.
2. Integration points owned by later phases are recorded in BACKLOG: the grounding verifier re-checks `summarize_for_handoff` output (09), workflow callers and fallbacks (09), clause texts passed to `phrase_response` come from the phase 06 policy pack.
