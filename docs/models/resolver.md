# Model card: transaction resolver

| Field | Value |
|---|---|
| Component | `TransactionResolver` port (`bank_agent.ports.models`) |
| Implementations | `resolver:lgbm` (champion `411b1d77d17b`); baseline `resolver:rules@1` (served by default) |
| Owner | ml |
| Trained by | `make train` (`bank-ml resolver train`); evaluated by `bank-ml resolver evaluate`; promoted by `make promote APPROVED_BY=...` |
| Full results | [`docs/evaluation/resolver.md`](../evaluation/resolver.md) (generated) |
| Decision record | [ADR 0016](../adr/0016-resolver-approach.md) |

## Intended use

Rank the session customer's own transactions against what the customer said about one of them, for two uses reported separately. `dispute` covers transactions inside the country's dispute window (`DSP-*-1`: MX 90, CO 60, AR 30 days). `payment_lookup` in `account_inquiry` covers payments and transfers inside `ACC-ALL-2` (92 days). A clear winner lets the workflow proceed to confirmation. Otherwise it shows up to three masked options, or asks for detail when nothing plausible matches. The resolver never fetches data and never decides a dispute; every write still needs confirmation, step-up, and a verified read-back.

## Data

- **Labels by construction.** Target transactions are sampled from gold (`transactions_serving`) with a salted hash. A description is generated from the known target by deterministic es (per country) and pt templates. Amounts are exact, rounded ("de como 15.200 pesos"), or in slang ("15 lucas", "15 mil pesos"). Merchants are exact, misspelled by one letter, or partial. Dates are relative, a weekday, "hace N días", explicit, or numeric and possibly ambiguous ("03/05"). There is sometimes a channel hint, and at least one of amount, merchant, or date is always given.
- **Descriptors** come from the engine's own model-off understanding (`application/understanding/descriptor.py`), so the resolver is trained and evaluated on what the engine actually extracts, parser misses included.
- **Target-absent queries.** 10% of dev and test queries remove the target from the candidates. The right behavior there is not to auto-select anything.
- **Scale.** 6,000 train, 1,934 dev, and 1,940 test queries across both uses, 30% of them in Portuguese. Gold has about 33 transactions per customer over three years, so candidate sets are small: a third of queries have one candidate and 81% have three or fewer.
- **Paraphrases** through the gateway are not generated (no provider). This is a pending human action.

## Splits and leakage prevention

Customers are split 70/15/15 by a salted hash, so no customer appears in two splits. A temporal cutoff (2026-01-01) with a 30-day gap puts train and dev reference instants before the cutoff and test instants after 2026-01-31, from test customers only. The dataset hash covers texts, candidates, targets, and descriptors, so a change in the understanding code makes a trained model stale and `evaluate` refuses it. The columns read are declared and pass the post-outcome leakage guard. `complaints.affected_product_id` is never read: it always names another customer's product.

## Models

| Model | Description |
|---|---|
| `resolver:rules@1` | Phase 09 baseline: amount, merchant word overlap, date, and channel points; a minimum score, a winner score, and a fixed margin |
| `resolver:lgbm` | LightGBM lambdarank (seeded, one thread, deterministic; 19 rounds by early stopping on dev NDCG@1) over 16 shared features: amount given, absolute and relative difference, currency match, amount closeness rank, date given, days outside the resolved range, date ambiguity, merchant fuzzy similarity (rapidfuzz), inferred category match, channel match, recency days and rank, same-day count, and candidate count. An evidence gate ranks only candidates that agree with at least one clue |

The clear winner uses softmax probabilities over the plausible candidates plus a "none of these" option (score 1.162), and the top probability must beat both the runner-up and the none option by a margin of 0.0036. The none score and the margin were chosen together on dev: the largest coverage with at most 2% wrong among auto-selected queries and at most 5% auto-selection on target-absent queries. On dev that gives 92.6% coverage, 0.17% wrong among auto-selected, and 2.6% target-absent auto-selection. The trees are served by a pure-Python evaluator in `bank_agent`, which matches LightGBM's own predictions to 1e-9 (integration test).

## Metrics (test split, 95% intervals resampling customers)

Queries with two or more candidates (dispute 652, payment lookup 676):

| Use | Model | Top-1 | MRR | Coverage (auto-selected) | Wrong-transaction rate | Correct clarify | Target absent, auto-selected |
|---|---|---|---|---|---|---|---|
| Dispute | `rules@1` | 0.989 [0.979, 0.995] | 0.990 | 0.793 [0.761, 0.824] | 0.003 [0.000, 0.008] | 0.948 (of 96) | 0.049 (of 41) |
| Dispute | `lgbm` | 1.000 [1.000, 1.000] | 1.000 | 0.913 [0.891, 0.934] | 0.000 [0.000, 0.000] | 1.000 (of 16) | 0.000 (of 41) |
| Payment lookup | `rules@1` | 0.989 [0.981, 0.997] | 0.989 | 0.769 [0.738, 0.798] | 0.000 | 0.940 (of 117) | 0.000 (of 39) |
| Payment lookup | `lgbm` | 1.000 [1.000, 1.000] | 1.000 | 0.936 [0.917, 0.954] | 0.001 [0.000, 0.006] | 1.000 (of 5) | 0.026 (of 39) |

- **Definitions.** Wrong-transaction rate is wrong auto-selections over all queries, target-absent ones included. Correct clarify is the share of non-auto-selected queries with a target whose target is among the three options shown.
- **Slices.** Language, country, candidate count, and each clue type are in the evaluation. Both models are at or near the ceiling in every slice.
- **Silver labels (secondary).** Of 8,523 `Transactions` and `Fees` complaints with a claimed amount, only 12 match any own transaction (same currency, amount within 1%, 60 days before the complaint), each uniquely. The synthetic complaints are, in effect, not linked to transactions. Precision of the 12 is pending human verification (`data/labeling/resolver_silver_sample.csv`, gitignored).

## Limitations

- The synthetic task is easy: few candidates per query, 24 merchant names, and descriptions built from exact facts. Both models sit near the ceiling on top-1, so the learned model's real gain is coverage (fewer clarifying questions) at an equal or lower wrong-transaction rate. Real customer descriptions will be harder.
- Descriptions come from templates, not people, and no language-model paraphrase was generated.
- Target-absent cells are small (39 to 41 queries per use), so their intervals are wide.
- Silver labels cannot measure the resolver on real complaints in this delivery.
- In production the true transaction may be outside the window or not yet posted; target-absent queries simulate only part of that.

## Ethical considerations

The resolver receives only the session customer's own transactions, fetched by the application through a context-bound repository, so it cannot reach another customer's data. A wrong auto-selection could open a dispute on the wrong charge, which is why the none option and the target-absent constraint exist, and why the confirmation step shows the chosen transaction before any write. Description examples in committed reports have every digit masked because they come from organizer data. The default stays on `resolver:rules@1` until phase 14 measures `resolver:lgbm` end to end (`WORKFLOW_RESOLVER=lgbm@champion` switches it on).
