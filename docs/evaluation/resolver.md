# Resolver evaluation

Generated 2026-09-27T20:10:04+00:00 from commit `2c19633` by `bank-ml resolver evaluate`. Do not edit by hand; rerun `make train` (or `bank-ml resolver evaluate`).

- Dataset `resolver-v1`, content hash `e862992cad4ee6c1`: train 6000, test 1940, dev 1934 queries; candidate count distribution: {1: 3254, 2: 2945, 3: 1831, 4: 995, 5: 485, 6: 210, 7: 94, 8: 32, 9: 18, 10: 4, 11: 4, 12: 1, 13: 1}.
- Evaluated artifact (champion): `resolver:lgbm@411b1d77d17b`; clear-winner margin 0.0036, chosen on dev for at most 2.0% wrong among auto-selected (dev coverage 92.6%, dev wrong 0.2%), together with the none-of-these score 1.1623 so that at most 5.0% of dev target-absent queries are auto-selected (dev: 2.6%).
- Labels are by construction: each description was generated from a known gold transaction (synthetic organizer data) with deterministic es and pt templates. 10% of dev and test queries remove the target from the candidates; any auto-selection there is wrong. Intervals are 95% bootstraps resampling customers.
- `rules@1` is evaluated at its shipped thresholds; `lgbm` at the dev-chosen margin. The test split was never used for any choice.

## Dispute (transactions in the dispute window) (test)

| Model | Top-1 | MRR | Coverage (auto) | Wrong-transaction rate | Wrong among auto | Correct clarify | Target absent, auto-selected | n (queries / customers) |
|---|---|---|---|---|---|---|---|---|
| `rules@1`, two or more candidates | 0.989 [0.979, 0.995] | 0.990 [0.982, 0.997] | 0.793 [0.761, 0.824] | 0.003 [0.000, 0.008] | 0.004 [0.000, 0.010] | 0.948 [0.898, 0.989] | 0.049 [0.000, 0.122] | 652 / 636 |
| `rules@1`, all queries | 0.989 [0.982, 0.996] | 0.990 [0.982, 0.996] | 0.795 [0.771, 0.821] | 0.003 [0.000, 0.007] | 0.004 [0.000, 0.009] | 0.941 [0.899, 0.978] | 0.045 [0.000, 0.106] | 973 / 952 |
| `lgbm`, two or more candidates | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.913 [0.891, 0.934] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 652 / 636 |
| `lgbm`, all queries | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.916 [0.896, 0.933] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 1.000 [1.000, 1.000] | 0.000 [0.000, 0.000] | 973 / 952 |

By language:

| Language | Queries | rules@1 top-1 / wrong rate | lgbm top-1 / wrong rate |
|---|---|---|---|
| es | 681 | 0.99 [0.97, 0.99] / 0.003 [0.000, 0.007] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| pt | 292 | 1.00 [0.99, 1.00] / 0.003 [0.000, 0.010] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |

By country:

| Country | Queries | rules@1 top-1 / wrong rate | lgbm top-1 / wrong rate |
|---|---|---|---|
| AR | 191 | 0.99 [0.97, 1.00] / 0.005 [0.000, 0.016] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| CO | 293 | 0.99 [0.97, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| MX | 489 | 0.99 [0.98, 1.00] / 0.004 [0.000, 0.010] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |

By candidate count:

| Candidates | Queries | rules@1 top-1 / wrong rate | lgbm top-1 / wrong rate |
|---|---|---|---|
| 1 | 321 | 0.99 [0.98, 1.00] / 0.003 [0.000, 0.009] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| 2-3 | 451 | 0.99 [0.98, 1.00] / 0.004 [0.000, 0.011] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| 4-6 | 188 | 0.99 [0.97, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| 7+ | 13 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |

By the amount clue given:

| Amount clue | Queries | rules@1 top-1 / wrong rate | lgbm top-1 / wrong rate |
|---|---|---|---|
| exact | 396 | 1.00 [1.00, 1.00] / 0.003 [0.000, 0.008] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| none | 177 | 0.95 [0.91, 0.98] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| rounded | 194 | 0.99 [0.98, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| slang | 206 | 1.00 [1.00, 1.00] / 0.010 [0.000, 0.024] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |

By the merchant clue given:

| Merchant clue | Queries | rules@1 top-1 / wrong rate | lgbm top-1 / wrong rate |
|---|---|---|---|
| exact | 109 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| misspelled | 106 | 0.97 [0.93, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| none | 638 | 0.99 [0.98, 1.00] / 0.003 [0.000, 0.008] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| partial | 120 | 1.00 [1.00, 1.00] / 0.008 [0.000, 0.025] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |

By the date clue given:

| Date clue | Queries | rules@1 top-1 / wrong rate | lgbm top-1 / wrong rate |
|---|---|---|---|
| days_ago | 101 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| explicit | 274 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| none | 216 | 0.99 [0.97, 1.00] / 0.005 [0.000, 0.014] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| numeric | 291 | 0.97 [0.95, 0.99] / 0.003 [0.000, 0.010] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| relative | 27 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| weekday | 64 | 1.00 [1.00, 1.00] / 0.016 [0.000, 0.047] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |

## Payment lookup (payments and transfers) (test)

| Model | Top-1 | MRR | Coverage (auto) | Wrong-transaction rate | Wrong among auto | Correct clarify | Target absent, auto-selected | n (queries / customers) |
|---|---|---|---|---|---|---|---|---|
| `rules@1`, two or more candidates | 0.989 [0.981, 0.997] | 0.989 [0.981, 0.995] | 0.769 [0.738, 0.798] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.940 [0.889, 0.975] | 0.000 [0.000, 0.000] | 676 / 654 |
| `rules@1`, all queries | 0.991 [0.984, 0.997] | 0.991 [0.984, 0.997] | 0.751 [0.722, 0.778] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.953 [0.917, 0.982] | 0.000 [0.000, 0.000] | 967 / 931 |
| `lgbm`, two or more candidates | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.936 [0.917, 0.954] | 0.001 [0.000, 0.006] | 0.002 [0.000, 0.005] | 1.000 [1.000, 1.000] | 0.026 [0.000, 0.077] | 676 / 654 |
| `lgbm`, all queries | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.922 [0.905, 0.939] | 0.002 [0.000, 0.005] | 0.002 [0.000, 0.006] | 1.000 [1.000, 1.000] | 0.028 [0.000, 0.069] | 967 / 931 |

By language:

| Language | Queries | rules@1 top-1 / wrong rate | lgbm top-1 / wrong rate |
|---|---|---|---|
| es | 671 | 0.99 [0.98, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.001 [0.000, 0.004] |
| pt | 296 | 0.99 [0.97, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.003 [0.000, 0.010] |

By country:

| Country | Queries | rules@1 top-1 / wrong rate | lgbm top-1 / wrong rate |
|---|---|---|---|
| AR | 183 | 0.99 [0.98, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| CO | 284 | 0.98 [0.97, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.007 [0.000, 0.018] |
| MX | 500 | 0.99 [0.99, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |

By candidate count:

| Candidates | Queries | rules@1 top-1 / wrong rate | lgbm top-1 / wrong rate |
|---|---|---|---|
| 1 | 291 | 1.00 [0.98, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.003 [0.000, 0.010] |
| 2-3 | 508 | 0.99 [0.98, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.002 [0.000, 0.006] |
| 4-6 | 159 | 0.99 [0.97, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| 7+ | 9 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |

By the amount clue given:

| Amount clue | Queries | rules@1 top-1 / wrong rate | lgbm top-1 / wrong rate |
|---|---|---|---|
| exact | 396 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.005 [0.000, 0.013] |
| none | 175 | 0.95 [0.91, 0.98] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| rounded | 213 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| slang | 183 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |

By the merchant clue given:

| Merchant clue | Queries | rules@1 top-1 / wrong rate | lgbm top-1 / wrong rate |
|---|---|---|---|
| none | 967 | 0.99 [0.98, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.002 [0.000, 0.005] |

By the date clue given:

| Date clue | Queries | rules@1 top-1 / wrong rate | lgbm top-1 / wrong rate |
|---|---|---|---|
| days_ago | 82 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.012 [0.000, 0.037] |
| explicit | 286 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| none | 205 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.005 [0.000, 0.015] |
| numeric | 303 | 0.97 [0.95, 0.99] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| relative | 26 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |
| weekday | 65 | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] | 1.00 [1.00, 1.00] / 0.000 [0.000, 0.000] |

## Dev split (used for early stopping, the margin, and promotion)

| Model | dev_top1 | dev_mrr | dev_coverage | dev_wrong_rate | dev_correct_clarify | dev_absent_false_auto |
|---|---|---|---|---|---|---|
| `rules@1` | 0.9880 | 0.9889 | 0.8087 | 0.0041 | 0.9349 | 0.0684 |
| `lgbm` | 0.9974 | 0.9983 | 0.9255 | 0.0016 | 0.9667 | 0.0256 |

## Silver labels (secondary)

8,523 `Transactions` and `Fees` complaints carry a claimed amount; 12 match at least one own transaction (same currency, amount within 1%, 60 days before the complaint), 12 exactly one. Silver-label precision **pending** (sheet written, 12 items, not yet verified). The sheet lives in `data/labeling/resolver_silver_sample.csv` (gitignored: organizer records). This is a secondary evaluation and partly circular: the descriptor carries the claimed amount that also defines the match.

| Model | Top-1 | MRR | Coverage (auto) | Wrong-transaction rate | Wrong among auto | Correct clarify | Target absent, auto-selected | n (queries / customers) |
|---|---|---|---|---|---|---|---|---|
| `rules@1` | 0.917 [0.750, 1.000] | 0.917 [0.750, 1.000] | 0.917 [0.750, 1.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | 0.000 [0.000, 0.000] | n/a | 12 / 12 |
| `lgbm` | 0.500 [0.250, 0.750] | 0.660 [0.458, 0.861] | 0.333 [0.083, 0.583] | 0.083 [0.000, 0.250] | 0.250 [0.000, 0.750] | 0.875 [0.625, 1.000] | n/a | 12 / 12 |

## Failure examples (test)

### `rules@1`

| Description (digits masked) | Use | Candidates | Target present | Wrong auto-selection | Target rank |
|---|---|---|---|---|---|
| Quiero reclamar una compra en Intrnet Plus | dispute | 1 | True | False | not ranked |
| Quiero reclamar una compra el ##/## | dispute | 4 | True | False | not ranked |
| No reconozco un cargo en Restauante El Buen Sabor | dispute | 3 | True | False | not ranked |
| Che, tengo un cargo el ##/## que no hice | dispute | 2 | True | False | 2 |
| No reconozco un cargo de US$ ###.## el ##/## | dispute | 1 | False | True | not ranked |
| No reconozco un cargo el ##/## | dispute | 2 | True | False | 2 |
| Hay un cobro raro en Empresa Teefónica, ayúdenme | dispute | 3 | True | False | not ranked |
| No reconozco lo que me cobraron en Tienda el miércoles de ### lucas | dispute | 2 | False | True | not ranked |
| Me cobraron el ##/## y no fui yo | dispute | 4 | True | False | not ranked |
| Quiero reclamar una compra el ##/## | dispute | 2 | True | False | not ranked |
| Me cobraram no dia ##/## e não fui eu pela internet | dispute | 1 | True | False | not ranked |
| Me cobraron de como ## dólares el ##/## y no fui yo | dispute | 1 | True | False | not ranked |

### `lgbm`

| Description (digits masked) | Use | Candidates | Target present | Wrong auto-selection | Target rank |
|---|---|---|---|---|---|
| Queria saber se o pagamento de $##.###.###,## há ## dias entrou | payment_lookup | 2 | False | True | not ranked |
| ¿Ya se acreditó la transferencia de $#.###.###,## que hice? | payment_lookup | 1 | False | True | not ranked |
