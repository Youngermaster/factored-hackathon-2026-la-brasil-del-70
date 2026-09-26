# bank-ml: learned components

## Responsibility

`bank-ml` trains, evaluates, and registers the learned components that the API loads through its `ModelRegistry` port:

- the intent router (phase 10);
- the transaction resolver that links a customer description to a transaction (phase 10).

Training runs log parameters, metrics, dataset hashes, and the git sha to MLflow. The API never imports this package: it loads registered artifacts by name and version, or by an alias such as `champion`, so a model can be replaced without workflow changes.

## Layout

| Path | Content |
|---|---|
| `src/bank_ml/` | The Python package; `cli.py` is the `bank-ml` entry point |
| `tests/unit/` | Unit tests |

Phase 10 adds `src/bank_ml/router`, `src/bank_ml/resolver`, and `src/bank_ml/common`.

## Dependencies

Heavy ML libraries (scikit-learn, LightGBM, MLflow) are added by phase 10, together with the code that uses them. sentence-transformers is never a dependency of the API runtime: it lives in an optional `ml` extra of `bank-agent`, added in phase 07 with the dense retriever, and is excluded from the API image.

## Public interfaces

- The `bank-ml` command. Today it exposes `version` and `--help`:

  ```bash
  uv run bank-ml --help
  uv run bank-ml version
  ```

- Phase 10 adds `train` and `register`, wired to `make train`.

## How to extend

- **New model:** add a pipeline module under `src/bank_ml/`, a training command, and an evaluation that reports on the dev and test splits. Register the artifact with a version; the API selects it through settings.
- **New command:** add a function decorated with `@app.command()` in `src/bank_ml/cli.py`.

## How to test

```bash
uv run pytest ml/tests -m unit
make test-unit
```

Coverage for `ml/src` is gated at 80% line coverage by `make check`.
