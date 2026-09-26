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
| `src/bank_evals/scenarios/model.py` | `Scenario`, version 1 of the scenario contract (`contracts/schemas/scenario.v1.json`) |
| `src/bank_evals/language_checks.py` | `portuguese_problems` and `spanish_problems`: lexical checks that a reply is natural pt-BR or Spanish, run over cassettes |
| `cassettes/` | Language model cassettes replayed by `CassetteLLM`; hand-authored fixtures until a provider is chosen ([README](cassettes/README.md)) |
| `tests/unit/` | Unit tests |

Phase 14 adds scenario generators and loaders, `src/bank_evals/systems`, graders, and reports.

`bank-evals` depends on `bank-agent` (a uv workspace dependency) for the domain vocabulary the scenarios share with the system under test, and, from phase 14, to run the proposed system in process. `bank-agent` never imports `bank-evals`.

## Public interfaces

- The `bank-eval` command. Today it exposes `version` and `--help`:

  ```bash
  uv run bank-eval --help
  uv run bank-eval version
  ```

- Phase 14 adds `run` and `publish`, wired to `make eval`.

## How to extend

- **New scenario set:** add scenario files that validate against `Scenario` (id, split, language and dialect, category, persona reference, facts, scripted turns or simulator instructions, fixtures, tool failure plan, expected outcome and state assertions, disclosures, expected handoff fields, provenance, review status) and a set hash, so reports can name the exact inputs.
- **New scenario field:** add it to `Scenario` as an optional field (additive, a minor version), run `make contracts`, and commit the regenerated schema with the change.
- **New system under test:** implement it against the same tool interfaces as the proposed system, so comparisons stay fair.
- **New command:** add a function decorated with `@app.command()` in `src/bank_evals/cli.py`.

## How to test

```bash
uv run pytest evals/tests -m unit
make test-unit
```

Coverage for `evals/src` is gated at 80% line coverage by `make check`.
