# Language model cassettes

Recorded language model calls, replayed by `CassetteLLM` (`services/api/src/bank_agent/adapters/llm/cassette.py`) so tests and evaluations are deterministic and never call a provider.

## Status: hand-authored fixtures only

The language model provider has not been chosen (human decision pending), so **no cassette here was recorded from a model**. Every file has `"provenance": "hand_authored_fixture"` and `"model_id": "fixture/hand-authored"`. The replies were written by the team to exercise parsing, replay, per-workflow coverage, and the Portuguese language check. They are not evidence of model quality and must never be reported as such.

Recording real cassettes is a pending human action in `docs/PROGRESS.md`: once a provider and key are chosen, record every case below against the chosen models and keep the fixtures only as long as tests need them.

## Layout

```text
evals/cassettes/
└── <prompt_id>/
    └── <version>/
        └── <cassette_id>.json
```

`cassette_id` is a SHA-256 over the prompt reference, the model id, the session language, and the canonical JSON of the redacted variables, so a file can only be replayed by exactly the call that produced it. A unit test recomputes it from each file's content.

| Field | Meaning |
|---|---|
| `provenance` | `recorded` or `hand_authored_fixture` |
| `note`, `labels` | Free text and labels (`workflow`, `case`: `normal`, `ambiguous`, or `out_of_scope`) |
| `prompt`, `model_id`, `language` | What was called |
| `kind`, `output_model` | `structured` with the output model name, or `text` |
| `variables` | The redacted variables, canonical JSON |
| `output` | The reply, redacted |
| `usage`, `latency_ms`, `repaired`, `recorded_at` | Call metadata (zero for fixtures) |

## Coverage

| Prompt | Cases |
|---|---|
| `extract_dispute_slots@1`, `extract_account_inquiry_slots@1`, `extract_card_support_slots@1`, `extract_credit_slots@1` | es and pt, each with a normal, an ambiguous, and an out-of-scope message (24 files) |
| `phrase_response@1` | es and pt for each of the four workflows (8 files), checked by `bank_evals.language_checks` |

## How to change fixtures

Edit the cases in `scripts/write_fixture_cassettes.py` and run it; never edit a JSON file by hand, because the id depends on the content. `uv run --frozen python scripts/write_fixture_cassettes.py --check` fails when the files are stale, and a unit test runs it.

## How to record real cassettes (after the provider decision)

1. Install the extra: `uv sync --all-packages --extra litellm`.
2. Set, in the shell or `.env` (never in a session): `LLM_PROVIDER=cassette`, `LLM_CASSETTE_MODE=record`, `LLM_PRIMARY_MODEL=<provider/model>`, `LLM_API_KEY_PRIMARY=<key>`.
3. Run the calls to record (phase 14 adds the evaluation command that drives them).
4. Check that every new file has `"provenance": "recorded"`, contains no personal data (variables and outputs are redacted before writing), and passes `uv run pytest services/api/tests/unit/adapters/llm/test_fixture_cassettes.py`.

Recording is refused in production settings.
