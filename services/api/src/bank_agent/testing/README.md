# bank_agent.testing

## Responsibility

Deterministic test doubles shared by the tests of every package and by the evaluation harness. They implement the ports exactly as documented, but from scripts instead of real dependencies.

## Public interfaces

| Module | Double | Port |
|---|---|---|
| `clock.py` | `FixedClock` (`now`, `advance`, `set`; forward only, UTC) | `Clock` |
| `ids.py` | `SequentialIdGenerator` (`case-000001`, one counter per kind) | `IdGenerator` |
| `fake_llm.py` | `FakeLLM`, `ScriptedResponse`, `ScriptedError`, `input_hash`, `canonical_variables` | `LLMClient` |
| `language.py` | `FakeLanguageDetector` | `LanguageDetector` |
| `models.py` | `FakeIntentRouter`, `FakeTransactionResolver` | `IntentRouter`, `TransactionResolver` |
| `telemetry.py` | `RecordingTelemetry` | `Telemetry` |

`FakeLLM` scripts responses per prompt reference and input hash (SHA-256 over the prompt reference and the canonical JSON of the variables), or per prompt with a wildcard. Scripts are queues whose last entry repeats. An unscripted call raises `FakeLLMScriptMissingError`; the fake never guesses. The phase 08 cassette client reuses `input_hash`.

## Rules

- Production layers (`domain` through `api` and `bootstrap`) never import this package, and this package imports only `domain` and `ports`. Two import-linter contracts enforce both directions.
- Whether the composition root may use `FakeLLM` for `LLM_PROVIDER=fake` outside tests is decided in phase 08.

## How to extend

Add a double next to the port it implements, make it pass that port's contract suite in `services/api/tests/contracts/`, and add unit tests under `services/api/tests/unit/testing/`.

## How to test

`uv run pytest services/api/tests/unit/testing`. Coverage gate: 90% line coverage.
