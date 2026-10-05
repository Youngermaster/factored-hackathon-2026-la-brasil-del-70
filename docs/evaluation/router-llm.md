# Router: classical routers against a hosted language model

Generated 2026-10-05T18:54:25+00:00 from commit `ea4bbb7` by `bank-ml router zero-shot`. Every section except the decision is generated; do not edit it by hand. Rerun `uv run --frozen bank-ml router zero-shot`: it replays the committed cassettes, so no key is needed.

Inputs:

- Dataset `router-v1`, content hash `5ec099abd3718810`: dev 286 items (68 seed groups), test 601 items (136 seed groups). All text is synthetic (team-authored seeds in es-MX, es-CO, es-AR, and pt-BR, with deterministic augmentation).
- Classical routers: `router:keyword@1` (threshold 0.6, fixed in code; served in production) and `router:tfidf@986872f0284f` (threshold 0.8838, chosen on dev at training).
- Prompt `classify_intent_fallback@1` (file sha256 `f1c9c03f237c`), no router candidates (zero-shot), temperature 0.0, at most 200 output tokens, called through the full gateway, so each message is redacted exactly as in production.
- Models: `azure/gpt-4.1-mini`, `azure/gpt-4o` (Azure OpenAI). Recorded calls: `ml/cassettes/router_llm/` (redacted, one JSON file per call).
- Prices: `services/api/config/llm_prices.yaml`, read from the Azure Retail Prices API on 2026-10-05 (region swedencentral). The table marks them unverified until a person confirms them; that only adds the gateway's conservative multiplier and does not change this report. Cost per 1,000 messages is the measured tokens of this workload times the list price: an **offline measurement**, not production spend.
- Intervals are 95% percentile bootstraps over whole seed groups (1,000 resamples). Dev fixed every choice: the model thresholds (error among covered at most 5%), the cascade thresholds, and the decision. Test only reports.

## Pre-registered decision rule

Committed in [`docs/plans/router-llm.md`](../plans/router-llm.md) before any model call and before any test number existed. The zero-shot model is a reference, never a serving candidate. A cascade (TF-IDF first, the model only below TF-IDF's threshold) is recommended for a default-off end-to-end dev trial only if every criterion holds on dev:

1. Macro-F1 gain over TF-IDF alone above 0.05, with the paired seed-group bootstrap 95% lower bound above 0.
2. High-stakes recall mean at most 0.02 below TF-IDF alone.
3. Confident misroutes into the write intents (`dispute_new`, `card_block`, `credit_application`) at most TF-IDF's count plus 1.
4. The model is called on at most 60% of messages.
5. Model call p95 latency at most 2,000 ms.
6. Cost at most 1.00 USD per 1,000 messages at list price.

When both models qualify, the higher dev macro-F1 wins unless the paired difference's interval contains 0, in which case the cheaper model wins. Test never changes the decision. No production default changes in this work: the team's rule needs an end-to-end dev gain first, so `keyword@1` keeps serving.

## Dev: the rule applied

| Criterion | `tfidf@986872f0284f then azure/gpt-4.1-mini` | `tfidf@986872f0284f then azure/gpt-4o` |
|---|---|---|
| Macro-F1 gain over TF-IDF above 0.05, paired 95% lower bound above 0 | +0.232 [+0.149, +0.351] (met) | +0.230 [+0.134, +0.352] (met) |
| High-stakes recall mean at most 0.02 below TF-IDF | 0.942 against 0.751 (met) | 0.942 against 0.751 (met) |
| Confident write-intent misroutes at most TF-IDF's plus 1 | 2 against 0 (not met) | 0 against 0 (met) |
| Model called on at most 60% of messages | 59.4% (met) | 59.4% (met) |
| Model call p95 at most 2,000 ms | 1,663 ms (met) | 1,883 ms (met) |
| Cost at most 1.00 USD per 1,000 messages (list price) | 0.2523 USD (met) | 1.8915 USD (not met) |
| Qualifies | no | no |

**Mechanical outcome on dev:** no cascade meets every criterion, so no end-to-end cascade trial is recommended.

## Model thresholds (chosen on dev)

| System | Threshold | Dev coverage | Dev error among covered | Target met |
|---|---|---|---|---|
| `zero-shot azure/gpt-4.1-mini` | 0.850 | 100.0% | 3.1% | yes |
| `tfidf@986872f0284f then azure/gpt-4.1-mini` | 0.950 | 90.0% | 1.3% | yes |
| `keyword@1 then azure/gpt-4.1-mini` | 0.850 | 100.0% | 0.6% | yes |
| `zero-shot azure/gpt-4o` | 0.900 | 100.0% | 4.5% | yes |
| `tfidf@986872f0284f then azure/gpt-4o` | 0.950 | 75.3% | 0.0% | yes |
| `keyword@1 then azure/gpt-4o` | 0.900 | 100.0% | 0.6% | yes |

For a cascade, the threshold applies to the model's stated confidence on the dev messages that reach the model; coverage and risk are over those messages.

## Dev split (every choice was made here)

| System | Accuracy | Macro-F1 | Workflow accuracy | Coverage | Error when acting | High-stakes recall (mean) | Confident write-intent misroutes | Model share | p50 / p95 ms per message | Cost per 1,000 messages (USD) |
|---|---|---|---|---|---|---|---|---|---|---|
| `keyword@1` | 0.388 [0.278, 0.513] | 0.378 [0.275, 0.440] | 0.531 [0.417, 0.634] | 0.444 [0.333, 0.553] | 0.299 [0.141, 0.484] | 0.464 | 11 of 286 | 0.0% | 0.17 / 0.24 | 0.0000 |
| `tfidf@986872f0284f` | 0.748 [0.641, 0.842] | 0.715 [0.584, 0.799] | 0.825 [0.738, 0.912] | 0.406 [0.303, 0.509] | 0.043 [0.000, 0.113] | 0.751 | 0 of 286 | 0.0% | 0.51 / 6.77 | 0.0000 |
| `zero-shot azure/gpt-4.1-mini` | 0.969 [0.931, 0.997] | 0.966 [0.903, 0.996] | 0.969 [0.928, 0.997] | 1.000 [1.000, 1.000] | 0.031 [0.003, 0.069] | 0.986 | 7 of 286 | 100.0% | 1,038 / 1,939 | 0.4226 |
| `tfidf@986872f0284f then azure/gpt-4.1-mini` | 0.951 [0.904, 0.986] | 0.947 [0.885, 0.984] | 0.955 [0.909, 0.990] | 0.941 [0.887, 0.979] | 0.026 [0.004, 0.060] | 0.942 | 2 of 286 | 59.4% | 807 / 1,491 | 0.2523 |
| `keyword@1 then azure/gpt-4.1-mini` | 0.864 [0.784, 0.936] | 0.872 [0.765, 0.940] | 0.937 [0.876, 0.986] | 1.000 [1.000, 1.000] | 0.136 [0.061, 0.221] | 0.848 | 11 of 286 | 55.6% | 758 / 1,535 | 0.2346 |
| `zero-shot azure/gpt-4o` | 0.955 [0.910, 0.993] | 0.955 [0.895, 0.991] | 0.965 [0.922, 0.997] | 1.000 [1.000, 1.000] | 0.045 [0.010, 0.093] | 0.986 | 1 of 286 | 100.0% | 1,151 / 1,804 | 3.1693 |
| `tfidf@986872f0284f then azure/gpt-4o` | 0.948 [0.898, 0.986] | 0.945 [0.887, 0.982] | 0.951 [0.898, 0.986] | 0.853 [0.768, 0.927] | 0.020 [0.000, 0.051] | 0.942 | 0 of 286 | 59.4% | 949 / 1,688 | 1.8915 |
| `keyword@1 then azure/gpt-4o` | 0.864 [0.782, 0.939] | 0.872 [0.766, 0.935] | 0.937 [0.875, 0.986] | 1.000 [1.000, 1.000] | 0.136 [0.060, 0.223] | 0.848 | 11 of 286 | 55.6% | 911 / 1,660 | 1.7584 |

## Test split (held out; report only)

| System | Accuracy | Macro-F1 | Workflow accuracy | Coverage | Error when acting | High-stakes recall (mean) | Confident write-intent misroutes | Model share | p50 / p95 ms per message | Cost per 1,000 messages (USD) |
|---|---|---|---|---|---|---|---|---|---|---|
| `keyword@1` | 0.393 [0.319, 0.470] | 0.395 [0.308, 0.447] | 0.574 [0.488, 0.653] | 0.491 [0.407, 0.569] | 0.339 [0.233, 0.450] | 0.471 | 33 of 601 | 0.0% | 0.10 / 0.15 | 0.0000 |
| `tfidf@986872f0284f` | 0.677 [0.598, 0.754] | 0.661 [0.575, 0.713] | 0.827 [0.768, 0.882] | 0.484 [0.410, 0.564] | 0.096 [0.037, 0.177] | 0.741 | 1 of 601 | 0.0% | 0.60 / 7.00 | 0.0000 |
| `zero-shot azure/gpt-4.1-mini` | 0.889 [0.837, 0.935] | 0.885 [0.819, 0.925] | 0.900 [0.849, 0.948] | 0.992 [0.980, 1.000] | 0.107 [0.063, 0.159] | 0.990 | 31 of 601 | 100.0% | 1,067 / 2,395 | 0.4240 |
| `tfidf@986872f0284f then azure/gpt-4.1-mini` | 0.879 [0.823, 0.927] | 0.873 [0.802, 0.918] | 0.918 [0.876, 0.956] | 0.923 [0.884, 0.958] | 0.095 [0.050, 0.145] | 0.966 | 11 of 601 | 51.6% | 715 / 1,718 | 0.2187 |
| `keyword@1 then azure/gpt-4.1-mini` | 0.759 [0.694, 0.823] | 0.761 [0.676, 0.813] | 0.872 [0.821, 0.925] | 0.995 [0.987, 1.000] | 0.241 [0.174, 0.310] | 0.824 | 58 of 601 | 50.9% | 698 / 1,800 | 0.2156 |
| `zero-shot azure/gpt-4o` | 0.937 [0.896, 0.968] | 0.936 [0.890, 0.969] | 0.947 [0.910, 0.977] | 0.997 [0.991, 1.000] | 0.062 [0.028, 0.100] | 0.993 | 23 of 601 | 100.0% | 1,136 / 1,943 | 3.1737 |
| `tfidf@986872f0284f then azure/gpt-4o` | 0.913 [0.868, 0.955] | 0.910 [0.857, 0.948] | 0.953 [0.916, 0.980] | 0.869 [0.815, 0.913] | 0.080 [0.039, 0.133] | 0.960 | 11 of 601 | 51.6% | 791 / 1,738 | 1.6379 |
| `keyword@1 then azure/gpt-4o` | 0.794 [0.729, 0.860] | 0.798 [0.718, 0.848] | 0.903 [0.857, 0.947] | 0.997 [0.991, 1.000] | 0.205 [0.145, 0.273] | 0.828 | 48 of 601 | 50.9% | 724 / 1,658 | 1.6126 |

Paired test macro-F1 difference against `tfidf@986872f0284f` (same items, seed groups resampled jointly):

| System | Macro-F1 minus TF-IDF |
|---|---|
| `keyword@1` | -0.266 [-0.358, -0.171] |
| `zero-shot azure/gpt-4.1-mini` | 0.224 [0.149, 0.316] |
| `tfidf@986872f0284f then azure/gpt-4.1-mini` | 0.212 [0.139, 0.296] |
| `keyword@1 then azure/gpt-4.1-mini` | 0.100 [0.018, 0.186] |
| `zero-shot azure/gpt-4o` | 0.275 [0.209, 0.356] |
| `tfidf@986872f0284f then azure/gpt-4o` | 0.250 [0.193, 0.327] |
| `keyword@1 then azure/gpt-4o` | 0.137 [0.065, 0.219] |

## Where the model helps

Test accuracy split by whether the classical router acts (at or above its threshold) or abstains. In the cascade, the model only sees the abstaining region.

| Region (test) | Items | `tfidf@986872f0284f` accuracy | `zero-shot azure/gpt-4.1-mini` accuracy | `zero-shot azure/gpt-4o` accuracy |
|---|---|---|---|---|
| `tfidf@986872f0284f` acts | 291 | 0.904 [0.828, 0.967] | 0.924 [0.854, 0.984] | 0.952 [0.895, 0.996] |
| `tfidf@986872f0284f` abstains | 310 | 0.465 [0.366, 0.576] | 0.855 [0.774, 0.919] | 0.923 [0.864, 0.968] |

| Region (test) | Items | `keyword@1` accuracy | `zero-shot azure/gpt-4.1-mini` accuracy | `zero-shot azure/gpt-4o` accuracy |
|---|---|---|---|---|
| `keyword@1` acts | 295 | 0.661 [0.546, 0.774] | 0.925 [0.867, 0.975] | 0.953 [0.908, 0.990] |
| `keyword@1` abstains | 306 | 0.134 [0.059, 0.215] | 0.853 [0.776, 0.925] | 0.922 [0.863, 0.970] |

## Per intent (test, F1)

| Intent | Workflow | n | `keyword@1` F1 | `tfidf@986872f0284f` F1 | `zero-shot azure/gpt-4.1-mini` F1 | `zero-shot azure/gpt-4o` F1 |
|---|---|---|---|---|---|---|
| `balance_inquiry` | account_inquiry | 33 | 0.53 | 0.95 | 0.94 | 1.00 |
| `card_block` (high stakes) | card_support | 33 | 0.66 | 0.72 | 0.90 | 0.94 |
| `card_replacement_request` (high stakes) | card_support | 37 | 0.65 | 0.73 | 1.00 | 1.00 |
| `card_status` | card_support | 40 | 0.79 | 0.61 | 0.86 | 0.98 |
| `card_unblock_request` (high stakes) | card_support | 34 | 0.64 | 0.74 | 0.97 | 0.97 |
| `credit_application` (high stakes) | credit | 40 | 0.26 | 0.60 | 0.95 | 0.95 |
| `credit_application_status` | credit | 38 | 0.00 | 0.54 | 0.95 | 0.97 |
| `credit_eligibility` | credit | 34 | 0.25 | 0.44 | 0.92 | 0.90 |
| `credit_product_info` | credit | 38 | 0.47 | 0.68 | 0.99 | 0.97 |
| `dispute_new` (high stakes) | dispute | 45 | 0.56 | 0.75 | 0.79 | 0.86 |
| `dispute_status` | dispute | 37 | 0.00 | 0.62 | 0.94 | 0.96 |
| `greeting_or_other` | shared | 28 | 0.18 | 0.75 | 0.96 | 1.00 |
| `human_request` (high stakes) | shared | 25 | 0.39 | 0.89 | 0.96 | 0.98 |
| `informational` | shared | 32 | 0.00 | 0.37 | 0.67 | 0.77 |
| `payment_status` | account_inquiry | 38 | 0.15 | 0.92 | 0.66 | 0.87 |
| `statement_request` | account_inquiry | 37 | 0.75 | 0.88 | 0.89 | 0.94 |
| `unsupported` | out_of_scope | 32 | 0.42 | 0.05 | 0.69 | 0.85 |

## High-stakes recall (test)

| Intent | `keyword@1` recall | `tfidf@986872f0284f` recall | `zero-shot azure/gpt-4.1-mini` recall | `zero-shot azure/gpt-4o` recall | `tfidf@986872f0284f then azure/gpt-4.1-mini` recall | `tfidf@986872f0284f then azure/gpt-4o` recall |
|---|---|---|---|---|---|---|
| `dispute_new` | 0.600 [0.255, 0.891] | 0.733 [0.425, 0.942] | 0.978 [0.935, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| `card_block` | 0.818 [0.588, 0.968] | 0.879 [0.677, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| `card_unblock_request` | 0.529 [0.171, 0.838] | 0.735 [0.414, 0.976] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] |
| `card_replacement_request` | 0.486 [0.118, 0.784] | 0.649 [0.297, 0.907] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.973 [0.912, 1.000] | 0.973 [0.917, 1.000] |
| `credit_application` | 0.150 [0.000, 0.391] | 0.650 [0.316, 0.913] | 1.000 [1.000, 1.000] | 1.000 [1.000, 1.000] | 0.825 [0.559, 1.000] | 0.825 [0.583, 1.000] |
| `human_request` | 0.240 [0.000, 0.538] | 0.800 [0.519, 1.000] | 0.960 [0.864, 1.000] | 0.960 [0.857, 1.000] | 1.000 [1.000, 1.000] | 0.960 [0.864, 1.000] |

## Out-of-scope slice (test)

| System | Out-of-scope recall | Confidently routed into a workflow |
|---|---|---|
| `keyword@1` | 0.375 [0.111, 0.750] | 0 of 32 |
| `tfidf@986872f0284f` | 0.031 [0.000, 0.100] | 0 of 32 |
| `zero-shot azure/gpt-4.1-mini` | 0.562 [0.148, 0.883] | 13 of 32 |
| `tfidf@986872f0284f then azure/gpt-4.1-mini` | 0.562 [0.154, 0.909] | 7 of 32 |
| `keyword@1 then azure/gpt-4.1-mini` | 0.688 [0.345, 0.968] | 9 of 32 |
| `zero-shot azure/gpt-4o` | 0.781 [0.438, 1.000] | 7 of 32 |
| `tfidf@986872f0284f then azure/gpt-4o` | 0.781 [0.452, 1.000] | 7 of 32 |
| `keyword@1 then azure/gpt-4o` | 0.844 [0.536, 1.000] | 5 of 32 |

## By language (test, accuracy)

| System | es (n 446 / 102) | pt (n 155 / 34) |
|---|---|---|
| `keyword@1` | 0.386 [0.305, 0.483] | 0.413 [0.244, 0.580] |
| `tfidf@986872f0284f` | 0.695 [0.608, 0.777] | 0.626 [0.466, 0.782] |
| `zero-shot azure/gpt-4.1-mini` | 0.886 [0.826, 0.939] | 0.897 [0.783, 0.974] |
| `tfidf@986872f0284f then azure/gpt-4.1-mini` | 0.854 [0.788, 0.919] | 0.948 [0.887, 0.994] |
| `zero-shot azure/gpt-4o` | 0.944 [0.901, 0.978] | 0.916 [0.820, 0.994] |
| `tfidf@986872f0284f then azure/gpt-4o` | 0.901 [0.842, 0.950] | 0.948 [0.880, 0.994] |

## By language (test, macro-F1)

| System | es (n 446 / 102) | pt (n 155 / 34) |
|---|---|---|
| `keyword@1` | 0.392 [0.305, 0.455] | 0.357 [0.208, 0.471] |
| `tfidf@986872f0284f` | 0.684 [0.579, 0.747] | 0.535 [0.405, 0.662] |
| `zero-shot azure/gpt-4.1-mini` | 0.877 [0.791, 0.924] | 0.898 [0.796, 0.975] |
| `tfidf@986872f0284f then azure/gpt-4.1-mini` | 0.846 [0.753, 0.896] | 0.948 [0.871, 0.989] |
| `zero-shot azure/gpt-4o` | 0.940 [0.891, 0.976] | 0.923 [0.829, 0.995] |
| `tfidf@986872f0284f then azure/gpt-4o` | 0.899 [0.823, 0.946] | 0.951 [0.873, 0.995] |

## By dialect (test, accuracy)

| System | es-AR (n 139 / 34) | es-CO (n 153 / 34) | es-MX (n 154 / 35) | pt-BR (n 155 / 34) |
|---|---|---|---|---|
| `keyword@1` | 0.360 [0.210, 0.517] | 0.431 [0.270, 0.617] | 0.364 [0.223, 0.503] | 0.413 [0.244, 0.580] |
| `tfidf@986872f0284f` | 0.734 [0.579, 0.868] | 0.725 [0.580, 0.868] | 0.630 [0.466, 0.781] | 0.626 [0.466, 0.782] |
| `zero-shot azure/gpt-4.1-mini` | 0.827 [0.694, 0.939] | 0.863 [0.741, 0.963] | 0.961 [0.892, 1.000] | 0.897 [0.783, 0.974] |
| `tfidf@986872f0284f then azure/gpt-4.1-mini` | 0.820 [0.691, 0.929] | 0.850 [0.736, 0.948] | 0.890 [0.787, 0.975] | 0.948 [0.887, 0.994] |
| `zero-shot azure/gpt-4o` | 0.906 [0.816, 0.978] | 0.954 [0.880, 1.000] | 0.968 [0.904, 1.000] | 0.916 [0.820, 0.994] |
| `tfidf@986872f0284f then azure/gpt-4o` | 0.906 [0.815, 0.978] | 0.908 [0.810, 0.993] | 0.890 [0.787, 0.975] | 0.948 [0.880, 0.994] |

## Workflow confusion by language (test)

### `zero-shot azure/gpt-4.1-mini`, es

| True \ predicted | account_inquiry | card_support | dispute | credit | shared | out_of_scope |
|---|---|---|---|---|---|---|
| **account_inquiry** | 63 | 4 | 8 | 0 | 0 | 1 |
| **card_support** | 4 | 105 | 0 | 0 | 0 | 0 |
| **dispute** | 0 | 0 | 53 | 4 | 0 | 0 |
| **credit** | 0 | 0 | 0 | 118 | 0 | 0 |
| **shared** | 0 | 12 | 4 | 0 | 48 | 0 |
| **out_of_scope** | 7 | 0 | 3 | 0 | 0 | 12 |

### `zero-shot azure/gpt-4.1-mini`, pt

| True \ predicted | account_inquiry | card_support | dispute | credit | shared | out_of_scope |
|---|---|---|---|---|---|---|
| **account_inquiry** | 24 | 1 | 7 | 0 | 0 | 0 |
| **card_support** | 0 | 35 | 0 | 0 | 0 | 0 |
| **dispute** | 0 | 0 | 24 | 0 | 0 | 1 |
| **credit** | 0 | 0 | 0 | 32 | 0 | 0 |
| **shared** | 0 | 0 | 0 | 0 | 21 | 0 |
| **out_of_scope** | 4 | 0 | 0 | 0 | 0 | 6 |

### `zero-shot azure/gpt-4o`, es

| True \ predicted | account_inquiry | card_support | dispute | credit | shared | out_of_scope |
|---|---|---|---|---|---|---|
| **account_inquiry** | 73 | 0 | 3 | 0 | 0 | 0 |
| **card_support** | 0 | 109 | 0 | 0 | 0 | 0 |
| **dispute** | 0 | 0 | 55 | 2 | 0 | 0 |
| **credit** | 0 | 0 | 0 | 118 | 0 | 0 |
| **shared** | 0 | 8 | 4 | 0 | 51 | 1 |
| **out_of_scope** | 0 | 0 | 3 | 0 | 0 | 19 |

### `zero-shot azure/gpt-4o`, pt

| True \ predicted | account_inquiry | card_support | dispute | credit | shared | out_of_scope |
|---|---|---|---|---|---|---|
| **account_inquiry** | 25 | 0 | 6 | 0 | 0 | 1 |
| **card_support** | 0 | 35 | 0 | 0 | 0 | 0 |
| **dispute** | 0 | 0 | 25 | 0 | 0 | 0 |
| **credit** | 0 | 0 | 0 | 32 | 0 | 0 |
| **shared** | 0 | 0 | 0 | 0 | 21 | 0 |
| **out_of_scope** | 4 | 0 | 0 | 0 | 0 | 6 |

### `tfidf@986872f0284f then azure/gpt-4.1-mini`, es

| True \ predicted | account_inquiry | card_support | dispute | credit | shared | out_of_scope |
|---|---|---|---|---|---|---|
| **account_inquiry** | 70 | 4 | 1 | 0 | 0 | 1 |
| **card_support** | 4 | 105 | 0 | 0 | 0 | 0 |
| **dispute** | 0 | 0 | 53 | 4 | 0 | 0 |
| **credit** | 0 | 0 | 4 | 114 | 0 | 0 |
| **shared** | 0 | 12 | 4 | 0 | 48 | 0 |
| **out_of_scope** | 7 | 0 | 3 | 0 | 0 | 12 |

### `tfidf@986872f0284f then azure/gpt-4.1-mini`, pt

| True \ predicted | account_inquiry | card_support | dispute | credit | shared | out_of_scope |
|---|---|---|---|---|---|---|
| **account_inquiry** | 31 | 1 | 0 | 0 | 0 | 0 |
| **card_support** | 0 | 35 | 0 | 0 | 0 | 0 |
| **dispute** | 0 | 0 | 25 | 0 | 0 | 0 |
| **credit** | 0 | 0 | 0 | 32 | 0 | 0 |
| **shared** | 0 | 0 | 0 | 0 | 21 | 0 |
| **out_of_scope** | 4 | 0 | 0 | 0 | 0 | 6 |

### `tfidf@986872f0284f then azure/gpt-4o`, es

| True \ predicted | account_inquiry | card_support | dispute | credit | shared | out_of_scope |
|---|---|---|---|---|---|---|
| **account_inquiry** | 76 | 0 | 0 | 0 | 0 | 0 |
| **card_support** | 0 | 109 | 0 | 0 | 0 | 0 |
| **dispute** | 0 | 0 | 55 | 2 | 0 | 0 |
| **credit** | 0 | 0 | 4 | 114 | 0 | 0 |
| **shared** | 0 | 9 | 4 | 0 | 50 | 1 |
| **out_of_scope** | 0 | 0 | 3 | 0 | 0 | 19 |

### `tfidf@986872f0284f then azure/gpt-4o`, pt

| True \ predicted | account_inquiry | card_support | dispute | credit | shared | out_of_scope |
|---|---|---|---|---|---|---|
| **account_inquiry** | 31 | 0 | 0 | 0 | 0 | 1 |
| **card_support** | 0 | 35 | 0 | 0 | 0 | 0 |
| **dispute** | 0 | 0 | 25 | 0 | 0 | 0 |
| **credit** | 0 | 0 | 0 | 32 | 0 | 0 |
| **shared** | 0 | 0 | 0 | 0 | 21 | 0 |
| **out_of_scope** | 4 | 0 | 0 | 0 | 0 | 6 |

## Calibration of the stated confidence (test)

The stated confidence is the model's own number for its top label. ECE uses 10 equal-width bins; empty bins are omitted.

| System | ECE (test) |
|---|---|
| `keyword@1` | 0.173 |
| `tfidf@986872f0284f` | 0.125 |
| `zero-shot azure/gpt-4.1-mini` | 0.056 |
| `tfidf@986872f0284f then azure/gpt-4.1-mini` | 0.077 |
| `keyword@1 then azure/gpt-4.1-mini` | 0.139 |
| `zero-shot azure/gpt-4o` | 0.021 |
| `tfidf@986872f0284f then azure/gpt-4o` | 0.043 |
| `keyword@1 then azure/gpt-4o` | 0.105 |

### `zero-shot azure/gpt-4.1-mini`

| Confidence bin | Items | Mean confidence | Accuracy |
|---|---|---|---|
| 0.7 to 0.8 | 5 | 0.800 | 0.400 |
| 0.8 to 0.9 | 68 | 0.896 | 0.515 |
| 0.9 to 1.0 | 528 | 0.952 | 0.941 |

### `zero-shot azure/gpt-4o`

| Confidence bin | Items | Mean confidence | Accuracy |
|---|---|---|---|
| 0.7 to 0.8 | 2 | 0.800 | 0.500 |
| 0.8 to 0.9 | 126 | 0.900 | 0.833 |
| 0.9 to 1.0 | 473 | 0.959 | 0.966 |

## Tokens, latency, and cost (test)

| System | Model calls (share) | Input / output tokens per call | Model call p50 / p95 ms | Failures | Repaired outputs | Cost per 1,000 messages (USD) | List price in / out per million (USD) |
|---|---|---|---|---|---|---|---|
| `zero-shot azure/gpt-4.1-mini` | 601 (100.0%) | 934 / 32 | 1,067 / 2,395 | 0 | 0 | 0.4240 | 0.40 / 1.60 (unverified, 2025-04-01) |
| `tfidf@986872f0284f then azure/gpt-4.1-mini` | 310 (51.6%) | 935 / 31 | 1,071 / 2,541 | 0 | 0 | 0.2187 | 0.40 / 1.60 (unverified, 2025-04-01) |
| `keyword@1 then azure/gpt-4.1-mini` | 306 (50.9%) | 934 / 31 | 1,075 / 2,597 | 0 | 0 | 0.2156 | 0.40 / 1.60 (unverified, 2025-04-01) |
| `zero-shot azure/gpt-4o` | 601 (100.0%) | 934 / 29 | 1,136 / 1,943 | 0 | 0 | 3.1737 | 3.025 / 12.10 (unverified, 2024-12-01) |
| `tfidf@986872f0284f then azure/gpt-4o` | 310 (51.6%) | 935 / 29 | 1,140 / 1,953 | 0 | 0 | 1.6379 | 3.025 / 12.10 (unverified, 2024-12-01) |
| `keyword@1 then azure/gpt-4o` | 306 (50.9%) | 934 / 28 | 1,141 / 1,953 | 0 | 0 | 1.6126 | 3.025 / 12.10 (unverified, 2024-12-01) |

Latency of a model call is the provider round trip recorded in the cassette, measured from the development machine under the recording concurrency, so it includes provider queueing. The committed cassettes were recorded on 2026-10-05: `azure/gpt-4.1-mini` on the evaluation account (East US, 8 calls in flight, capped at 130 per minute) and `azure/gpt-4o` on the production account (Sweden Central, 2 calls in flight, capped at 35 per minute). Production calls `azure/gpt-4.1-mini` in Sweden Central from the Azure VM, so its latency differs. The classical routers were timed in process on the machine that generated this report. None of these numbers includes the rest of a turn.

## Label audit candidates (test)

Canonical test seeds where every model agrees at stated confidence of at least 0.9 and disagrees with the team's label. They are candidates for the human validation sheet (`ml/corpus/router/validation/`), never relabeled automatically: the disagreement may be a model error, an ambiguous message, or a labeling convention the prompt does not state.

| Locale | Text | Team label | Models | Confidence |
|---|---|---|---|---|
| es-AR | ¿Me dan un préstamo personal? | `credit_eligibility` | `credit_application` | 0.95 |
| es-CO | ¿Cómo es el proceso de un reclamo por transacción no reconocida? | `informational` | `dispute_new` | 0.95 |
| es-AR | Exijo que me devuelvan la guita ya, quiero un contracargo garantizado | `unsupported` | `dispute_new` | 0.95 |
| pt-BR | Preciso de uma declaração da conta pra apresentar no trabalho | `unsupported` | `statement_request` | 0.95 |
| es-CO | ¿El bloqueo de la tarjeta es temporal o definitivo? | `informational` | `card_status` | 0.90 |
| pt-BR | Oi, fiz uma transferência de R$ 150 e a pessoa diz que não recebeu | `payment_status` | `dispute_new` | 0.90 |

## Limitations

- All text is synthetic and team-authored, and the same people wrote the seeds and the keyword patterns. The pt-BR seeds await native review, and the 200-item human validation sheet has no labels yet.
- The prompt gives label names without definitions, so the model cannot know team conventions such as `informational` against `credit_product_info`. Part of its error measures label ambiguity, not understanding. A prompt with definitions or examples would be a new version, chosen on dev.
- The stated confidence is coarse (few distinct values), so the model thresholds are coarse.
- Dev has 68 seed groups, so the dev intervals that drive the decision are wide.
- The latency is from one machine, one day, and one region, under the recording concurrency. It is not a production service level.
- Cost covers the routing call only, at list price. It excludes the other model calls of a turn and any discount or reservation.
- This is a component evaluation. Whether better routing changes safe automated resolution end to end needs a `bank-eval` dev run, which the team's rule requires before any default changes.

## Decision

<!-- decision:begin (hand-written; kept when the report is regenerated) -->

Written on 2026-10-05 by the router benchmark track, after the dev rule was applied mechanically. The test numbers below were read after the rule was applied, and they do not change the outcome.

**Outcome: production keeps `keyword@1`, and no cascade trial is recommended yet.**

- **The pre-registered rule recommends no cascade.** The `gpt-4.1-mini` cascade misses criterion 3 by one item: it made 2 confident write-intent misroutes on dev, where TF-IDF made 0 and the limit was 1. The `gpt-4o` cascade misses criterion 6: it costs 1.89 USD per 1,000 messages against a limit of 1.00. The rule is not relaxed after seeing the numbers.
- **The default stays.** This is a component benchmark. The team's rule changes a default only after an end-to-end dev gain, so the served router stays `keyword@1`.

What the evidence shows (test, offline, synthetic text):

1. **The hosted model understands far more requests than the classical routers.**
   - Zero-shot macro-F1 is 0.885 [0.819, 0.925] for `gpt-4.1-mini` and 0.936 [0.890, 0.969] for `gpt-4o`. TF-IDF reaches 0.661 [0.575, 0.713] and `keyword@1` 0.395 [0.308, 0.447].
   - The paired gains over TF-IDF are +0.224 [0.149, 0.316] and +0.275 [0.209, 0.356].
   - The gap is widest in Portuguese: pt accuracy is 0.897 and 0.916 against 0.626 for TF-IDF.
   - The model is also stronger on the long-tail credit and dispute-status intents.
2. **The model guesses when the classical routers abstain.**
   - Zero-shot covers almost every message with high stated confidence. It confidently routes 31 (`gpt-4.1-mini`) and 23 (`gpt-4o`) of 601 messages into the wrong write intent. TF-IDF does this once and `keyword@1` 33 times.
   - It sends 13 and 7 of the 32 out-of-scope messages into a workflow. Neither classical router confidently sends any of the 32 into a workflow, so those customers get a clarifying question or the out-of-scope answer.
   - Higher accuracy does not mean safer routing.
3. **The cascade puts the model where it helps.**
   - TF-IDF acts on 291 test messages at 0.904 accuracy. On the 310 messages where it abstains, it would be right 0.465 of the time, against 0.855 for `gpt-4.1-mini` and 0.923 for `gpt-4o`.
   - The `gpt-4.1-mini` cascade reaches macro-F1 0.873 [0.802, 0.918] at 0.22 USD per 1,000 messages (half of zero-shot). The model is called for 52% of messages, and the p95 latency per message is 1.7 s.
   - The cascade still makes 11 confident write-intent misroutes against TF-IDF's 1, which confirms the dev signal behind criterion 3.
4. **Cost, latency, and calibration.**
   - Zero-shot `gpt-4o` costs 7.5 times as much as `gpt-4.1-mini` (3.17 against 0.42 USD per 1,000 messages) for +0.05 macro-F1.
   - The model call has a p95 of about 2 s, against under 1 ms in process for the classical routers.
   - The stated confidence of `gpt-4o` is close to calibrated (ECE 0.021, against 0.125 for TF-IDF), but it uses few distinct values, so its thresholds are coarse.

Where AI and deterministic logic each belong, on this evidence:

- **The classical router and deterministic dispatch stay as the first line.** They are free, run in under a millisecond, keep the text on the VM, and abstain instead of guessing.
- **The model's value is concentrated where the classical router abstains,** and in Portuguese.
- **A misroute never authorizes anything.** Every write still needs confirmation, step-up, and a verified read-back, so a misroute costs a clarifying turn, not an unauthorized action.

Next steps are recorded in `docs/BACKLOG.md`:

1. A human audit of the label audit candidates.
2. A new prompt version with intent definitions, aimed at the write-intent confusions (for example `informational` and `payment_status` read as `dispute_new`), chosen on dev and re-checked against the same rule.
3. Only if a cascade then passes the rule: a default-off flag in the engine and an end-to-end `bank-eval` dev run before any default changes.

<!-- decision:end -->
