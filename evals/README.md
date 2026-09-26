# bank-evals: evaluation harness

## Responsibility

`bank-evals` measures the system against baselines on the same held-out workload, using the outcome definitions from the brief: safe automated resolution, containment, escalation quality, unsafe outcomes, and operating efficiency (phase 14). It owns:

- scenario sets, including normal, ambiguous, and escalation cases in Spanish and Portuguese;
- the systems under test (baselines and the proposed system), resolved from the API composition root;
- graders and the report generator.

Offline measurements, simulations, and projected savings are always labeled separately. The harness is separate from the test suite and runs through `make eval`.

## Layout

| Path | Content |
|---|---|
| `src/bank_evals/` | The Python package; `cli.py` is the `bank-eval` entry point |
| `tests/unit/` | Unit tests |

Phase 14 adds `src/bank_evals/scenarios`, `src/bank_evals/systems`, graders, and reports.

## Public interfaces

- The `bank-eval` command. Today it exposes `version` and `--help`:

  ```bash
  uv run bank-eval --help
  uv run bank-eval version
  ```

- Phase 14 adds `run` and `publish`, wired to `make eval`.

## How to extend

- **New scenario set:** add scenario files with their expected outcomes and a set hash, so reports can name the exact inputs.
- **New system under test:** implement it against the same tool interfaces as the proposed system, so comparisons stay fair.
- **New command:** add a function decorated with `@app.command()` in `src/bank_evals/cli.py`.

## How to test

```bash
uv run pytest evals/tests -m unit
make test-unit
```

Coverage for `evals/src` is gated at 80% line coverage by `make check`.
