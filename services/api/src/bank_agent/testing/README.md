# bank_agent.testing

## Responsibility

Deterministic test doubles shared by the tests of every package and by the evaluation harness. They implement the ports exactly as documented, but from scripts instead of real dependencies.

## Public interfaces

| Module | Double | Port |
|---|---|---|
| `clock.py` | `FixedClock` (`now`, `advance`, `set`; forward only, UTC) | `Clock` |
| `ids.py` | `SequentialIdGenerator` (`case-000001`, one counter per kind) | `IdGenerator` |
| `fake_llm.py` | `FakeLLM`, `ScriptedResponse`, `ScriptedError`, and re-exports of `input_hash` and `canonical_variables` (which live in `domain/intelligence.py`) | `LLMClient` |
| `language.py` | `FakeLanguageDetector` | `LanguageDetector` |
| `models.py` | `FakeIntentRouter`, `FakeTransactionResolver` | `IntentRouter`, `TransactionResolver` |
| `telemetry.py` | `RecordingTelemetry` | `Telemetry` |
| `credit.py` | `FakeRiskEstimator`, `ScriptedRisk`, `feature_digest`, `FakeEligibilityPolicy` | `RiskEstimator`, `EligibilityPolicy` |

`FakeLLM` scripts responses per prompt reference and input hash (SHA-256 over the prompt reference and the canonical JSON of the variables), or per prompt with a wildcard. Scripts are queues whose last entry repeats. An unscripted call raises `FakeLLMScriptMissingError`; the fake never guesses. The canonicalization lives in the domain so the cassette adapter uses the same function.

`FakeRiskEstimator` scripts estimates per `feature_digest` (SHA-256 over the canonical JSON of the features), with a default, and raises `RiskEstimatorUnavailableError` when built with `unavailable=True`. `FakeEligibilityPolicy` stands in for the synthetic eligibility service until phase 06: it applies the guards the port documents (a product without self-service eligibility, missing facts, or a missing or `unknown` estimate lead to review or `insufficient_data`) and then returns the outcome scripted per product code. Both take a clock and an id generator.

## Rules

- Production layers (`domain` through `api` and `bootstrap`) never import this package, and this package imports only `domain` and `ports`. Two import-linter contracts enforce both directions.
- `FakeLLM` stays a test double (phase 08 decision): tests and the evaluation harness inject it into the composition root through `LlmOverrides`, and with `LLM_PROVIDER=fake` and nothing injected the root uses `UnconfiguredLLMClient`, which refuses every call.

## How to extend

Add a double next to the port it implements, make it pass that port's contract suite in `services/api/tests/contracts/`, and add unit tests under `services/api/tests/unit/testing/`.

## How to test

`uv run pytest services/api/tests/unit/testing`. Coverage gate: 90% line coverage.
