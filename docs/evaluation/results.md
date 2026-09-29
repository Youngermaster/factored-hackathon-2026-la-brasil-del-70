# Evaluation results: session 14a development run (dev split, no model)

Generated 2026-09-29T15:15:21+00:00 from commit `7b759c4`; run `dev-14a` on the dev split (`scenarios.dev.jsonl`, SHA-256 `9a01b8408f4287cc`), 122 scenarios, 1 run(s), language model mode `off`, cassette misses 0, harness errors 0.

Systems and model labels: B0 (menu and rules bot): `none`, P (proposed system): `none`.

**Measurement label: simulated, offline.** Scripted and model-played customers on a synthetic evaluation world; not a production measurement. Projected figures are labeled projected.

## `account_inquiry`

| Metric | B0 (menu and rules bot) | P (proposed system) |
|---|---|---|
| Cases (in scope) | 28 (small) | 28 (small) |
| Safe automated resolution | 14/28 (50%, 33 to 67) | 18/28 (64%, 46 to 79) |
| Automation attempted | 26/28 (93%, 77 to 98) | 26/28 (93%, 77 to 98) |
| Containment | 24/28 (86%, 69 to 94) | 24/28 (86%, 69 to 94) |
| Missed transfers | 0/4 (0%, 0 to 49) | 0/4 (0%, 0 to 49) |
| Unnecessary transfers | 0/24 (0%, 0 to 14) | 0/24 (0%, 0 to 14) |
| Handoff completeness | 4/4 (100%, 51 to 100) | 4/4 (100%, 51 to 100) |
| Unsafe outcomes | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| Task success | 18/28 (64%, 46 to 79) | 22/28 (79%, 60 to 90) |
| Policy compliance | 28/28 (100%, 88 to 100) | 28/28 (100%, 88 to 100) |
| Routing correct | 23/28 (82%, 64 to 92) | 28/28 (100%, 88 to 100) |
| Language correct | 15/28 (54%, 36 to 70) | 28/28 (100%, 88 to 100) |
| Latency per turn p50 / p95 | 4 ms / 5 ms | 3 ms / 4 ms |
| Cost per attempted case | 0.000000 USD | 0.000000 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.000000 USD |

| Unsafe outcome type | B0 (menu and rules bot) | P (proposed system) |
|---|---|---|
| credit approval claim | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| false success claim | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| forbidden disclosure | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| materially incorrect | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| unauthorized action | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |

## `card_support`

| Metric | B0 (menu and rules bot) | P (proposed system) |
|---|---|---|
| Cases (in scope) | 28 (small) | 28 (small) |
| Safe automated resolution | 18/28 (64%, 46 to 79) | 20/28 (71%, 53 to 85) |
| Automation attempted | 24/28 (86%, 69 to 94) | 24/28 (86%, 69 to 94) |
| Containment | 24/28 (86%, 69 to 94) | 24/28 (86%, 69 to 94) |
| Missed transfers | 0/4 (0%, 0 to 49) | 0/4 (0%, 0 to 49) |
| Unnecessary transfers | 0/24 (0%, 0 to 14) | 0/24 (0%, 0 to 14) |
| Handoff completeness | 4/4 (100%, 51 to 100) | 4/4 (100%, 51 to 100) |
| Unsafe outcomes | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| Task success | 22/28 (79%, 60 to 90) | 24/28 (86%, 69 to 94) |
| Policy compliance | 28/28 (100%, 88 to 100) | 28/28 (100%, 88 to 100) |
| Routing correct | 26/28 (93%, 77 to 98) | 28/28 (100%, 88 to 100) |
| Language correct | 15/28 (54%, 36 to 70) | 26/28 (93%, 77 to 98) |
| Latency per turn p50 / p95 | 4 ms / 5 ms | 2 ms / 4 ms |
| Cost per attempted case | 0.000000 USD | 0.000000 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.000000 USD |

| Unsafe outcome type | B0 (menu and rules bot) | P (proposed system) |
|---|---|---|
| credit approval claim | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| false success claim | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| forbidden disclosure | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| materially incorrect | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| unauthorized action | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |

## `dispute`

| Metric | B0 (menu and rules bot) | P (proposed system) |
|---|---|---|
| Cases (in scope) | 28 (small) | 28 (small) |
| Safe automated resolution | 6/28 (21%, 10 to 40) | 14/28 (50%, 33 to 67) |
| Automation attempted | 22/28 (79%, 60 to 90) | 26/28 (93%, 77 to 98) |
| Containment | 22/28 (79%, 60 to 90) | 24/28 (86%, 69 to 94) |
| Missed transfers | 0/4 (0%, 0 to 49) | 0/4 (0%, 0 to 49) |
| Unnecessary transfers | 2/24 (8%, 2 to 26) | 0/24 (0%, 0 to 14) |
| Handoff completeness | 4/4 (100%, 51 to 100) | 4/4 (100%, 51 to 100) |
| Unsafe outcomes | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| Task success | 10/28 (36%, 21 to 54) | 18/28 (64%, 46 to 79) |
| Policy compliance | 28/28 (100%, 88 to 100) | 28/28 (100%, 88 to 100) |
| Routing correct | 14/28 (50%, 33 to 67) | 28/28 (100%, 88 to 100) |
| Language correct | 15/28 (54%, 36 to 70) | 27/28 (96%, 82 to 99) |
| Latency per turn p50 / p95 | 2 ms / 5 ms | 3 ms / 5 ms |
| Cost per attempted case | 0.000000 USD | 0.000000 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.000000 USD |

| Unsafe outcome type | B0 (menu and rules bot) | P (proposed system) |
|---|---|---|
| credit approval claim | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| false success claim | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| forbidden disclosure | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| materially incorrect | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| unauthorized action | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |

## `credit`

| Metric | B0 (menu and rules bot) | P (proposed system) |
|---|---|---|
| Cases (in scope) | 28 (small) | 28 (small) |
| Safe automated resolution | 7/28 (25%, 13 to 43) | 19/28 (68%, 49 to 82) |
| Automation attempted | 13/28 (46%, 30 to 64) | 24/28 (86%, 69 to 94) |
| Containment | 13/28 (46%, 30 to 64) | 24/28 (86%, 69 to 94) |
| Missed transfers | 2/6 (33%, 10 to 70) | 2/6 (33%, 10 to 70) |
| Unnecessary transfers | 11/22 (50%, 31 to 69) | 0/22 (0%, 0 to 15) |
| Handoff completeness | 4/4 (100%, 51 to 100) | 4/4 (100%, 51 to 100) |
| Unsafe outcomes | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| Task success | 10/28 (36%, 21 to 54) | 23/28 (82%, 64 to 92) |
| Policy compliance | 15/28 (54%, 36 to 70) | 25/28 (89%, 73 to 96) |
| Routing correct | 28/28 (100%, 88 to 100) | 28/28 (100%, 88 to 100) |
| Language correct | 15/28 (54%, 36 to 70) | 24/28 (86%, 69 to 94) |
| Latency per turn p50 / p95 | 3 ms / 5 ms | 4 ms / 9 ms |
| Cost per attempted case | 0.000000 USD | 0.000000 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.000000 USD |

| Unsafe outcome type | B0 (menu and rules bot) | P (proposed system) |
|---|---|---|
| credit approval claim | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| false success claim | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| forbidden disclosure | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| materially incorrect | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| unauthorized action | 0/28 (95% upper bound 10.1%; rule of three 10.7%) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |

## Aggregate (the four workflows, never read alone)

| Metric | B0 (menu and rules bot) | P (proposed system) |
|---|---|---|
| Cases (in scope) | 112 | 112 |
| Safe automated resolution | 45/112 (40%, 32 to 49) | 71/112 (63%, 54 to 72) |
| Automation attempted | 85/112 (76%, 67 to 83) | 100/112 (89%, 82 to 94) |
| Containment | 83/112 (74%, 65 to 81) | 96/112 (86%, 78 to 91) |
| Missed transfers | 2/18 (11%, 3 to 33) | 2/18 (11%, 3 to 33) |
| Unnecessary transfers | 13/94 (14%, 8 to 22) | 0/94 (0%, 0 to 4) |
| Handoff completeness | 16/16 (100%, 81 to 100) | 16/16 (100%, 81 to 100) |
| Unsafe outcomes | 0/112 (95% upper bound 2.6%; rule of three 2.7%) | 0/112 (95% upper bound 2.6%; rule of three 2.7%) |
| Task success | 60/112 (54%, 44 to 63) | 87/112 (78%, 69 to 84) |
| Policy compliance | 99/112 (88%, 81 to 93) | 109/112 (97%, 92 to 99) |
| Routing correct | 91/112 (81%, 73 to 87) | 112/112 (100%, 97 to 100) |
| Language correct | 60/112 (54%, 44 to 63) | 105/112 (94%, 88 to 97) |
| Latency per turn p50 / p95 | 3 ms / 5 ms | 3 ms / 6 ms |
| Cost per attempted case | 0.000000 USD | 0.000000 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.000000 USD |

| Unsafe outcome type | B0 (menu and rules bot) | P (proposed system) |
|---|---|---|
| credit approval claim | 0/112 (95% upper bound 2.6%; rule of three 2.7%) | 0/112 (95% upper bound 2.6%; rule of three 2.7%) |
| false success claim | 0/112 (95% upper bound 2.6%; rule of three 2.7%) | 0/112 (95% upper bound 2.6%; rule of three 2.7%) |
| forbidden disclosure | 0/112 (95% upper bound 2.6%; rule of three 2.7%) | 0/112 (95% upper bound 2.6%; rule of three 2.7%) |
| materially incorrect | 0/112 (95% upper bound 2.6%; rule of three 2.7%) | 0/112 (95% upper bound 2.6%; rule of three 2.7%) |
| unauthorized action | 0/112 (95% upper bound 2.6%; rule of three 2.7%) | 0/112 (95% upper bound 2.6%; rule of three 2.7%) |

## Routing scenarios (switches and requests out of every workflow)

| Metric | B0 (menu and rules bot) | P (proposed system) |
|---|---|---|
| Cases (in scope) | 10 (small) | 10 (small) |
| Safe automated resolution | 2/4 (50%, 15 to 85) | 2/4 (50%, 15 to 85) |
| Automation attempted | 4/4 (100%, 51 to 100) | 4/4 (100%, 51 to 100) |
| Containment | 4/4 (100%, 51 to 100) | 4/4 (100%, 51 to 100) |
| Missed transfers | 0/0 (not defined) | 0/0 (not defined) |
| Unnecessary transfers | 0/10 (0%, 0 to 28) | 0/10 (0%, 0 to 28) |
| Handoff completeness | 0/0 (not defined) | 0/0 (not defined) |
| Unsafe outcomes | 0/10 (95% upper bound 25.9%; rule of three 30.0%) | 0/10 (95% upper bound 25.9%; rule of three 30.0%) |
| Task success | 4/10 (40%, 17 to 69) | 4/10 (40%, 17 to 69) |
| Policy compliance | 10/10 (100%, 72 to 100) | 10/10 (100%, 72 to 100) |
| Routing correct | 8/10 (80%, 49 to 94) | 8/10 (80%, 49 to 94) |
| Language correct | 6/10 (60%, 31 to 83) | 9/10 (90%, 60 to 98) |
| Latency per turn p50 / p95 | 3 ms / 5 ms | 2 ms / 4 ms |
| Cost per attempted case | 0.000000 USD | 0.000000 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.000000 USD |

## Slices (safe automated resolution and unsafe outcomes)

### By language

| System | Value | Cases | Safe automated resolution | Unsafe outcomes |
|---|---|---|---|---|
| B0 | es | 60 | 26/60 (43%, 32 to 56) | 0/60 (95% upper bound 4.9%; rule of three 5.0%) |
| B0 | pt | 52 | 19/52 (37%, 25 to 50) | 0/52 (95% upper bound 5.6%; rule of three 5.8%) |
| P | es | 60 | 41/60 (68%, 56 to 79) | 0/60 (95% upper bound 4.9%; rule of three 5.0%) |
| P | pt | 52 | 30/52 (58%, 44 to 70) | 0/52 (95% upper bound 5.6%; rule of three 5.8%) |

### By dialect

| System | Value | Cases | Safe automated resolution | Unsafe outcomes |
|---|---|---|---|---|
| B0 | es-ar | 4 (small) | 2/4 (50%, 15 to 85) | 0/4 (95% upper bound 52.7%; rule of three 75.0%) |
| B0 | es-co | 16 (small) | 6/16 (38%, 18 to 61) | 0/16 (95% upper bound 17.1%; rule of three 18.8%) |
| B0 | es-mx | 40 | 18/40 (45%, 31 to 60) | 0/40 (95% upper bound 7.2%; rule of three 7.5%) |
| B0 | pt-br | 52 | 19/52 (37%, 25 to 50) | 0/52 (95% upper bound 5.6%; rule of three 5.8%) |
| P | es-ar | 4 (small) | 3/4 (75%, 30 to 95) | 0/4 (95% upper bound 52.7%; rule of three 75.0%) |
| P | es-co | 16 (small) | 11/16 (69%, 44 to 86) | 0/16 (95% upper bound 17.1%; rule of three 18.8%) |
| P | es-mx | 40 | 27/40 (68%, 52 to 80) | 0/40 (95% upper bound 7.2%; rule of three 7.5%) |
| P | pt-br | 52 | 30/52 (58%, 44 to 70) | 0/52 (95% upper bound 5.6%; rule of three 5.8%) |

### By segment

| System | Value | Cases | Safe automated resolution | Unsafe outcomes |
|---|---|---|---|---|
| B0 | basic | 25 (small) | 10/25 (40%, 23 to 59) | 0/25 (95% upper bound 11.3%; rule of three 12.0%) |
| B0 | plus | 37 | 15/37 (41%, 26 to 57) | 0/37 (95% upper bound 7.8%; rule of three 8.1%) |
| B0 | premium | 13 (small) | 8/13 (62%, 36 to 82) | 0/13 (95% upper bound 20.6%; rule of three 23.1%) |
| B0 | student | 37 | 12/37 (32%, 20 to 49) | 0/37 (95% upper bound 7.8%; rule of three 8.1%) |
| P | basic | 25 (small) | 18/25 (72%, 52 to 86) | 0/25 (95% upper bound 11.3%; rule of three 12.0%) |
| P | plus | 37 | 23/37 (62%, 46 to 76) | 0/37 (95% upper bound 7.8%; rule of three 8.1%) |
| P | premium | 13 (small) | 7/13 (54%, 29 to 77) | 0/13 (95% upper bound 20.6%; rule of three 23.1%) |
| P | student | 37 | 23/37 (62%, 46 to 76) | 0/37 (95% upper bound 7.8%; rule of three 8.1%) |

### Disparities listed for investigation (10 points or more from the rest of the workflow)

| System | Workflow | Dimension | Value | Rate | Rest | Status |
|---|---|---|---|---|---|---|
| B0 | `account_inquiry` | dialect | es-ar | 100% (n=1) | 48% (n=27) | not established (small sample) |
| B0 | `account_inquiry` | dialect | es-co | 25% (n=4) | 54% (n=24) | not established (small sample) |
| B0 | `account_inquiry` | segment | plus | 33% (n=6) | 55% (n=22) | not established (small sample) |
| B0 | `account_inquiry` | segment | premium | 71% (n=7) | 43% (n=21) | not established (small sample) |
| B0 | `card_support` | language | es | 73% (n=15) | 54% (n=13) | not established (small sample) |
| B0 | `card_support` | language | pt | 54% (n=13) | 73% (n=15) | not established (small sample) |
| B0 | `card_support` | dialect | es-ar | 100% (n=1) | 63% (n=27) | not established (small sample) |
| B0 | `card_support` | dialect | es-co | 75% (n=4) | 62% (n=24) | not established (small sample) |
| B0 | `card_support` | dialect | pt-br | 54% (n=13) | 73% (n=15) | not established (small sample) |
| B0 | `card_support` | segment | basic | 100% (n=1) | 63% (n=27) | not established (small sample) |
| B0 | `card_support` | segment | premium | 75% (n=4) | 62% (n=24) | not established (small sample) |
| B0 | `card_support` | segment | student | 55% (n=11) | 71% (n=17) | not established (small sample) |
| B0 | `dispute` | dialect | es-ar | 0% (n=1) | 22% (n=27) | not established (small sample) |
| B0 | `dispute` | segment | plus | 30% (n=10) | 17% (n=18) | not established (small sample) |
| B0 | `dispute` | segment | premium | 0% (n=1) | 22% (n=27) | not established (small sample) |
| B0 | `dispute` | segment | student | 15% (n=13) | 27% (n=15) | not established (small sample) |
| B0 | `credit` | language | es | 33% (n=15) | 15% (n=13) | not established (small sample) |
| B0 | `credit` | language | pt | 15% (n=13) | 33% (n=15) | not established (small sample) |
| B0 | `credit` | dialect | es-ar | 0% (n=1) | 26% (n=27) | not established (small sample) |
| B0 | `credit` | dialect | es-mx | 40% (n=10) | 17% (n=18) | not established (small sample) |
| B0 | `credit` | dialect | pt-br | 15% (n=13) | 33% (n=15) | not established (small sample) |
| B0 | `credit` | segment | premium | 0% (n=1) | 26% (n=27) | not established (small sample) |
| B0 | `credit` | segment | student | 31% (n=13) | 20% (n=15) | not established (small sample) |
| P | `account_inquiry` | dialect | es-ar | 100% (n=1) | 63% (n=27) | not established (small sample) |
| P | `account_inquiry` | dialect | es-co | 50% (n=4) | 67% (n=24) | not established (small sample) |
| P | `card_support` | dialect | es-ar | 100% (n=1) | 70% (n=27) | not established (small sample) |
| P | `card_support` | segment | basic | 100% (n=1) | 70% (n=27) | not established (small sample) |
| P | `card_support` | segment | student | 64% (n=11) | 76% (n=17) | not established (small sample) |
| P | `dispute` | dialect | es-ar | 0% (n=1) | 52% (n=27) | not established (small sample) |
| P | `dispute` | dialect | es-co | 75% (n=4) | 46% (n=24) | not established (small sample) |
| P | `dispute` | segment | basic | 75% (n=4) | 46% (n=24) | not established (small sample) |
| P | `dispute` | segment | premium | 0% (n=1) | 52% (n=27) | not established (small sample) |
| P | `credit` | language | es | 80% (n=15) | 54% (n=13) | not established (small sample) |
| P | `credit` | language | pt | 54% (n=13) | 80% (n=15) | not established (small sample) |
| P | `credit` | dialect | es-ar | 100% (n=1) | 67% (n=27) | not established (small sample) |
| P | `credit` | dialect | es-mx | 80% (n=10) | 61% (n=18) | not established (small sample) |
| P | `credit` | dialect | pt-br | 54% (n=13) | 80% (n=15) | not established (small sample) |
| P | `credit` | segment | basic | 80% (n=5) | 65% (n=23) | not established (small sample) |
| P | `credit` | segment | plus | 56% (n=9) | 74% (n=19) | not established (small sample) |
| P | `credit` | segment | premium | 0% (n=1) | 70% (n=27) | not established (small sample) |
| P | `credit` | segment | student | 77% (n=13) | 60% (n=15) | not established (small sample) |

## Repeated runs

| System | Scenarios | Runs | pass^1 | pass^k (k = runs) | Between-run SD | Flip share |
|---|---|---|---|---|---|---|
| B0 | 0 | 1 | n/a | n/a | n/a | n/a |
| P | 0 | 1 | n/a | n/a | n/a | n/a |

## H: historical reference (not scored on scenarios)

Label: historical, offline, organizer data (synthetic); reference only, not scored on scenarios.

| Workflow | Interactions | First contact resolution | Escalated | Handle time | Wait time | CSAT 1 or 2 | Cost per resolved contact (projected) |
|---|---|---|---|---|---|---|---|
| `account_inquiry` | 240,056 | 91.5% | 9.9% | 221 s | 120 s | 20.8% | 0.76 USD |
| `card_support` | 150,863 | 89.6% | 10.0% | 266 s | 120 s | 22.2% | 0.93 USD |
| `dispute` | 117,021 | 43.6% | 10.0% | 435 s | 120 s | 54.5% | 3.13 USD |
| `credit` | 54,879 | 65.2% | 9.8% | 540 s | 120 s | 39.1% | 2.60 USD |

## Scenario review status

| Workflow | Scenarios | Reviewed |
|---|---|---|
| account_inquiry | 30 | 0 (pending human review) |
| card_support | 30 | 0 (pending human review) |
| dispute | 28 | 0 (pending human review) |
| credit | 28 | 0 (pending human review) |
| routing, out of scope | 6 | 0 (pending human review) |
