# 0013: LiteLLM behind a port with composable decorators

- Status: accepted
- Date: 2026-09-26

## Context

The system needs language model calls for slot extraction, fallback intent classification, escalation signal detection, reply phrasing in Spanish and Portuguese, and handoff summaries, across four workflows. The provider and model are not chosen: the human has left the provider undecided, and phase 14 chooses models by evaluation. Every call must be bounded in time, retried only when that can help, protected against a failing provider, capped in cost, traced, stripped of personal data, and replayable offline for tests and evaluations. CLAUDE.md section 5 requires cross-cutting behavior to be added by wrapping a port, never inside business code.

## Considered options

1. **Provider SDKs called directly from workflow code** (for example the Anthropic or OpenAI SDK). Simple at first. Every call site repeats timeouts, retries, error mapping, and cost logic; switching or adding a provider touches workflow code; offline replay needs a mock per SDK.
2. **One provider SDK behind the `LLMClient` port.** Keeps workflows provider-free, but ties the adapter to one vendor before the evaluation has chosen one, and a fallback provider needs a second adapter.
3. **LiteLLM behind the `LLMClient` port, with reliability, cost, privacy, and tracing as decorators that implement the same port.** One adapter speaks to many providers through one request shape; each concern is a small, separately tested class; the composition root stacks them from settings.
4. **An LLM gateway service or framework (a proxy server or an agent framework).** Adds a process or a large abstraction whose retry, caching, and prompt handling overlap with the policy-driven engine and are harder to test deterministically.

## Decision

Option 3. Workflows depend only on `LLMClient`. `PromptedLLMClient` holds the provider-neutral logic (prompt rendering, the language directive, JSON Schema from the Pydantic output model, one repair attempt), and `LiteLLMCompletion` is the only code that knows LiteLLM. Decorators, outermost first: redaction, budget guard, tracing, cost accounting, fallback, then per provider a circuit breaker, bounded retry, and timeout. `FakeLLM` (tests) and `CassetteLLM` (record and replay) implement the same port, so tests and evaluations never call a provider.

LiteLLM 1.102.1 (MIT) measured 84 MB installed, 170 MB with its dependencies, so it is an optional `litellm` extra of `bank-agent`, pinned exactly, imported lazily on the first call, with its own retries off and its bundled model map used so importing it fetches nothing. It is not installed by `make setup`, and CI audits every extra.

## Consequences

- Swapping or adding a provider is a settings change plus a price table entry; workflow code does not change.
- Each concern is testable alone with fake clocks and scripted clients, and a test asserts the stack order.
- Prices are data (`services/api/config/llm_prices.yaml`) with a source and a verification flag; unverified and unknown prices are charged conservatively.
- LiteLLM is a large, security-sensitive dependency (it handles provider keys and pulls many packages). Keeping it optional limits exposure, but enabling a live provider requires a human review of the pinned version and its advisories.
- LiteLLM's translation of `response_format` differs per provider; structured output still works when a provider ignores it, because the schema is also in the prompt and every reply is validated.
- The provider-neutral client makes a direct SDK adapter possible later (a new `ChatCompletion` implementation) if LiteLLM proves unsuitable.
