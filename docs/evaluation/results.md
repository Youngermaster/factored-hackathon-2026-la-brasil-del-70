# Evaluation results: session 14b test run (test split, local model qwen2.5:7b-instruct)

Generated 2026-09-29T20:37:10+00:00 from commit `6bc2e9d`; run `test-local` on the test split (`scenarios.test.jsonl`, SHA-256 `292c7c0b17c3f04d`), 332 scenarios, 3 run(s), language model mode `record`, cassette misses 0, harness errors 0.

Systems and model labels: B0 (menu and rules bot): `none`, P (proposed system): `ollama/qwen2.5:7b-instruct (litellm)`, B1 (naive LLM agent): `ollama/qwen2.5:7b-instruct (litellm)`.

**Measurement label: simulated, offline.** Scripted and model-played customers on a synthetic evaluation world; not a production measurement. Projected figures are labeled projected.

## `account_inquiry`

| Metric | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| Cases (in scope) | 76 | 76 | 76 |
| Safe automated resolution | 42/76 (55%, 44 to 66) | 18/76 (24%, 16 to 34) | 54/76 (71%, 60 to 80) |
| Automation attempted | 63/76 (83%, 73 to 90) | 75/76 (99%, 93 to 100) | 65/76 (86%, 76 to 92) |
| Containment | 60/76 (79%, 69 to 87) | 75/76 (99%, 93 to 100) | 62/76 (82%, 71 to 89) |
| Missed transfers | 0/14 (0%, 0 to 22) | 13/14 (93%, 69 to 99) | 0/14 (0%, 0 to 22) |
| Unnecessary transfers | 2/62 (3%, 1 to 11) | 0/62 (0%, 0 to 6) | 0/62 (0%, 0 to 6) |
| Handoff completeness | 14/14 (100%, 78 to 100) | 0/1 (0%, 0 to 79) | 14/14 (100%, 78 to 100) |
| Unsafe outcomes | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 17/76 (22.4%, exact 95% 13.6 to 33.4) | 2/76 (2.6%, exact 95% 0.3 to 9.2) |
| Task success | 56/76 (74%, 63 to 82) | 24/76 (32%, 22 to 43) | 68/76 (89%, 81 to 95) |
| Policy compliance | 76/76 (100%, 95 to 100) | 76/76 (100%, 95 to 100) | 76/76 (100%, 95 to 100) |
| Routing correct | 58/76 (76%, 66 to 84) | 0/0 (not defined) | 71/76 (93%, 86 to 97) |
| Language correct | 47/76 (62%, 51 to 72) | 73/76 (96%, 89 to 99) | 73/76 (96%, 89 to 99) |
| Latency per turn p50 / p95 | 5 ms / 20 ms | 8763 ms / 14421 ms | 2851 ms / 9451 ms |
| Cost per attempted case | 0.000000 USD | 0.000000 USD | 0.000000 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.000000 USD | 0.000000 USD |

| Unsafe outcome type | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| credit approval claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| false success claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| forbidden disclosure | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 2/76 (2.6%, exact 95% 0.3 to 9.2) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| materially incorrect | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 13/76 (17.1%, exact 95% 9.4 to 27.5) | 2/76 (2.6%, exact 95% 0.3 to 9.2) |
| unauthorized action | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 2/76 (2.6%, exact 95% 0.3 to 9.2) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |

## `card_support`

| Metric | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| Cases (in scope) | 76 | 76 | 76 |
| Safe automated resolution | 43/76 (57%, 45 to 67) | 12/76 (16%, 9 to 26) | 40/76 (53%, 42 to 63) |
| Automation attempted | 68/76 (89%, 81 to 95) | 75/76 (99%, 93 to 100) | 55/76 (72%, 61 to 81) |
| Containment | 61/76 (80%, 70 to 88) | 73/76 (96%, 89 to 99) | 51/76 (67%, 56 to 77) |
| Missed transfers | 2/17 (12%, 3 to 34) | 16/17 (94%, 73 to 99) | 3/17 (18%, 6 to 41) |
| Unnecessary transfers | 0/59 (0%, 0 to 6) | 2/59 (3%, 1 to 12) | 11/59 (19%, 11 to 30) |
| Handoff completeness | 15/15 (100%, 80 to 100) | 0/1 (0%, 0 to 79) | 12/14 (86%, 60 to 96) |
| Unsafe outcomes | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 5/76 (6.6%, exact 95% 2.2 to 14.7) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| Task success | 58/76 (76%, 66 to 84) | 12/76 (16%, 9 to 26) | 48/76 (63%, 52 to 73) |
| Policy compliance | 76/76 (100%, 95 to 100) | 72/76 (95%, 87 to 98) | 76/76 (100%, 95 to 100) |
| Routing correct | 65/76 (86%, 76 to 92) | 0/0 (not defined) | 62/76 (82%, 71 to 89) |
| Language correct | 47/76 (62%, 51 to 72) | 76/76 (100%, 95 to 100) | 76/76 (100%, 95 to 100) |
| Latency per turn p50 / p95 | 5 ms / 18 ms | 5931 ms / 9459 ms | 1940 ms / 6996 ms |
| Cost per attempted case | 0.000000 USD | 0.000000 USD | 0.000000 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.000000 USD | 0.000000 USD |

| Unsafe outcome type | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| credit approval claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| false success claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 2/76 (2.6%, exact 95% 0.3 to 9.2) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| forbidden disclosure | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 1/76 (1.3%, exact 95% 0.0 to 7.1) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| materially incorrect | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| unauthorized action | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 2/76 (2.6%, exact 95% 0.3 to 9.2) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |

## `dispute`

| Metric | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| Cases (in scope) | 76 | 76 | 76 |
| Safe automated resolution | 27/76 (36%, 26 to 47) | 2/76 (3%, 1 to 9) | 34/76 (45%, 34 to 56) |
| Automation attempted | 68/76 (89%, 81 to 95) | 76/76 (100%, 95 to 100) | 63/76 (83%, 73 to 90) |
| Containment | 59/76 (78%, 67 to 86) | 75/76 (99%, 93 to 100) | 50/76 (66%, 55 to 75) |
| Missed transfers | 4/14 (29%, 12 to 55) | 13/14 (93%, 69 to 99) | 2/14 (14%, 4 to 40) |
| Unnecessary transfers | 7/62 (11%, 6 to 22) | 0/62 (0%, 0 to 6) | 14/62 (23%, 14 to 34) |
| Handoff completeness | 10/10 (100%, 72 to 100) | 0/1 (0%, 0 to 79) | 12/12 (100%, 76 to 100) |
| Unsafe outcomes | 3/76 (3.9%, exact 95% 0.8 to 11.1) | 14/76 (18.4%, exact 95% 10.5 to 29.0) | 4/76 (5.3%, exact 95% 1.5 to 12.9) |
| Task success | 40/76 (53%, 42 to 63) | 2/76 (3%, 1 to 9) | 50/76 (66%, 55 to 75) |
| Policy compliance | 76/76 (100%, 95 to 100) | 22/76 (29%, 20 to 40) | 76/76 (100%, 95 to 100) |
| Routing correct | 61/76 (80%, 70 to 88) | 0/0 (not defined) | 65/76 (86%, 76 to 92) |
| Language correct | 47/76 (62%, 51 to 72) | 75/76 (99%, 93 to 100) | 76/76 (100%, 95 to 100) |
| Latency per turn p50 / p95 | 5 ms / 15 ms | 8395 ms / 10443 ms | 1917 ms / 13935 ms |
| Cost per attempted case | 0.000000 USD | 0.000000 USD | 0.000000 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.000000 USD | 0.000000 USD |

| Unsafe outcome type | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| credit approval claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| false success claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| forbidden disclosure | 3/76 (3.9%, exact 95% 0.8 to 11.1) | 2/76 (2.6%, exact 95% 0.3 to 9.2) | 3/76 (3.9%, exact 95% 0.8 to 11.1) |
| materially incorrect | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| unauthorized action | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 12/76 (15.8%, exact 95% 8.4 to 26.0) | 1/76 (1.3%, exact 95% 0.0 to 7.1) |

## `credit`

| Metric | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| Cases (in scope) | 76 | 76 | 76 |
| Safe automated resolution | 16/76 (21%, 13 to 31) | 7/76 (9%, 5 to 18) | 49/76 (64%, 53 to 74) |
| Automation attempted | 28/76 (37%, 27 to 48) | 75/76 (99%, 93 to 100) | 74/76 (97%, 91 to 99) |
| Containment | 28/76 (37%, 27 to 48) | 68/76 (89%, 81 to 95) | 57/76 (75%, 64 to 83) |
| Missed transfers | 4/19 (21%, 9 to 43) | 12/19 (63%, 41 to 81) | 2/19 (11%, 3 to 31) |
| Unnecessary transfers | 33/57 (58%, 45 to 70) | 1/57 (2%, 0 to 9) | 2/57 (4%, 1 to 12) |
| Handoff completeness | 7/15 (47%, 25 to 70) | 0/7 (0%, 0 to 35) | 17/17 (100%, 82 to 100) |
| Unsafe outcomes | 1/76 (1.3%, exact 95% 0.0 to 7.1) | 54/76 (71.1%, exact 95% 59.5 to 80.9) | 2/76 (2.6%, exact 95% 0.3 to 9.2) |
| Task success | 19/76 (25%, 17 to 36) | 14/76 (18%, 11 to 29) | 66/76 (87%, 77 to 93) |
| Policy compliance | 35/76 (46%, 35 to 57) | 27/76 (36%, 26 to 47) | 70/76 (92%, 84 to 96) |
| Routing correct | 72/76 (95%, 87 to 98) | 0/0 (not defined) | 73/76 (96%, 89 to 99) |
| Language correct | 47/76 (62%, 51 to 72) | 74/76 (97%, 91 to 99) | 71/76 (93%, 86 to 97) |
| Latency per turn p50 / p95 | 4 ms / 20 ms | 8657 ms / 14675 ms | 4608 ms / 8935 ms |
| Cost per attempted case | 0.000000 USD | 0.000000 USD | 0.000000 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.000000 USD | 0.000000 USD |

| Unsafe outcome type | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| credit approval claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 32/76 (42.1%, exact 95% 30.9 to 54.0) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| false success claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| forbidden disclosure | 1/76 (1.3%, exact 95% 0.0 to 7.1) | 33/76 (43.4%, exact 95% 32.1 to 55.3) | 1/76 (1.3%, exact 95% 0.0 to 7.1) |
| materially incorrect | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 4/76 (5.3%, exact 95% 1.5 to 12.9) | 1/76 (1.3%, exact 95% 0.0 to 7.1) |
| unauthorized action | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 25/76 (32.9%, exact 95% 22.5 to 44.6) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |

## Aggregate (the four workflows, never read alone)

| Metric | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| Cases (in scope) | 304 | 304 | 304 |
| Safe automated resolution | 128/304 (42%, 37 to 48) | 39/304 (13%, 10 to 17) | 177/304 (58%, 53 to 64) |
| Automation attempted | 227/304 (75%, 69 to 79) | 301/304 (99%, 97 to 100) | 257/304 (85%, 80 to 88) |
| Containment | 208/304 (68%, 63 to 73) | 291/304 (96%, 93 to 97) | 220/304 (72%, 67 to 77) |
| Missed transfers | 10/64 (16%, 9 to 26) | 54/64 (84%, 74 to 91) | 7/64 (11%, 5 to 21) |
| Unnecessary transfers | 42/240 (18%, 13 to 23) | 3/240 (1%, 0 to 4) | 27/240 (11%, 8 to 16) |
| Handoff completeness | 46/54 (85%, 73 to 92) | 0/10 (0%, 0 to 28) | 55/57 (96%, 88 to 99) |
| Unsafe outcomes | 4/304 (1.3%, exact 95% 0.4 to 3.3) | 90/304 (29.6%, exact 95% 24.5 to 35.1) | 8/304 (2.6%, exact 95% 1.1 to 5.1) |
| Task success | 173/304 (57%, 51 to 62) | 52/304 (17%, 13 to 22) | 232/304 (76%, 71 to 81) |
| Policy compliance | 263/304 (87%, 82 to 90) | 197/304 (65%, 59 to 70) | 298/304 (98%, 96 to 99) |
| Routing correct | 256/304 (84%, 80 to 88) | 0/0 (not defined) | 271/304 (89%, 85 to 92) |
| Language correct | 188/304 (62%, 56 to 67) | 298/304 (98%, 96 to 99) | 296/304 (97%, 95 to 99) |
| Latency per turn p50 / p95 | 5 ms / 18 ms | 7650 ms / 13581 ms | 2322 ms / 10383 ms |
| Cost per attempted case | 0.000000 USD | 0.000000 USD | 0.000000 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.000000 USD | 0.000000 USD |

| Unsafe outcome type | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| credit approval claim | 0/304 (95% upper bound 1.0%; rule of three 1.0%) | 32/304 (10.5%, exact 95% 7.3 to 14.5) | 0/304 (95% upper bound 1.0%; rule of three 1.0%) |
| false success claim | 0/304 (95% upper bound 1.0%; rule of three 1.0%) | 2/304 (0.7%, exact 95% 0.1 to 2.4) | 0/304 (95% upper bound 1.0%; rule of three 1.0%) |
| forbidden disclosure | 4/304 (1.3%, exact 95% 0.4 to 3.3) | 38/304 (12.5%, exact 95% 9.0 to 16.8) | 4/304 (1.3%, exact 95% 0.4 to 3.3) |
| materially incorrect | 0/304 (95% upper bound 1.0%; rule of three 1.0%) | 17/304 (5.6%, exact 95% 3.3 to 8.8) | 3/304 (1.0%, exact 95% 0.2 to 2.9) |
| unauthorized action | 0/304 (95% upper bound 1.0%; rule of three 1.0%) | 41/304 (13.5%, exact 95% 9.9 to 17.8) | 1/304 (0.3%, exact 95% 0.0 to 1.8) |

## Routing scenarios (switches and requests out of every workflow)

| Metric | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| Cases (in scope) | 28 (small) | 28 (small) | 28 (small) |
| Safe automated resolution | 8/12 (67%, 39 to 86) | 1/12 (8%, 1 to 35) | 12/12 (100%, 76 to 100) |
| Automation attempted | 12/12 (100%, 76 to 100) | 12/12 (100%, 76 to 100) | 12/12 (100%, 76 to 100) |
| Containment | 12/12 (100%, 76 to 100) | 11/12 (92%, 65 to 99) | 12/12 (100%, 76 to 100) |
| Missed transfers | 0/0 (not defined) | 0/0 (not defined) | 0/0 (not defined) |
| Unnecessary transfers | 2/28 (7%, 2 to 23) | 4/28 (14%, 6 to 31) | 1/28 (4%, 1 to 18) |
| Handoff completeness | 0/0 (not defined) | 0/0 (not defined) | 0/0 (not defined) |
| Unsafe outcomes | 3/28 (10.7%, exact 95% 2.3 to 28.2) | 2/28 (7.1%, exact 95% 0.9 to 23.5) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| Task success | 13/28 (46%, 30 to 64) | 13/28 (46%, 30 to 64) | 14/28 (50%, 33 to 67) |
| Policy compliance | 28/28 (100%, 88 to 100) | 23/28 (82%, 64 to 92) | 28/28 (100%, 88 to 100) |
| Routing correct | 19/28 (68%, 49 to 82) | 0/0 (not defined) | 24/28 (86%, 69 to 94) |
| Language correct | 17/28 (61%, 42 to 76) | 28/28 (100%, 88 to 100) | 26/28 (93%, 77 to 98) |
| Latency per turn p50 / p95 | 4 ms / 10 ms | 6593 ms / 15701 ms | 2144 ms / 8290 ms |
| Cost per attempted case | 0.000000 USD | 0.000000 USD | 0.000000 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.000000 USD | 0.000000 USD |

## Slices (safe automated resolution and unsafe outcomes)

### By language

| System | Value | Cases | Safe automated resolution | Unsafe outcomes |
|---|---|---|---|---|
| B0 | es | 188 | 81/188 (43%, 36 to 50) | 3/188 (1.6%, exact 95% 0.3 to 4.6) |
| B0 | pt | 116 | 47/116 (41%, 32 to 50) | 1/116 (0.9%, exact 95% 0.0 to 4.7) |
| P | es | 188 | 114/188 (61%, 54 to 67) | 6/188 (3.2%, exact 95% 1.2 to 6.8) |
| P | pt | 116 | 63/116 (54%, 45 to 63) | 2/116 (1.7%, exact 95% 0.2 to 6.1) |
| B1 | es | 188 | 27/188 (14%, 10 to 20) | 57/188 (30.3%, exact 95% 23.8 to 37.4) |
| B1 | pt | 116 | 12/116 (10%, 6 to 17) | 33/116 (28.4%, exact 95% 20.5 to 37.6) |

### By dialect

| System | Value | Cases | Safe automated resolution | Unsafe outcomes |
|---|---|---|---|---|
| B0 | es-ar | 48 | 21/48 (44%, 31 to 58) | 0/48 (95% upper bound 6.1%; rule of three 6.2%) |
| B0 | es-co | 60 | 26/60 (43%, 32 to 56) | 1/60 (1.7%, exact 95% 0.0 to 8.9) |
| B0 | es-mx | 80 | 34/80 (42%, 32 to 53) | 2/80 (2.5%, exact 95% 0.3 to 8.7) |
| B0 | pt-br | 116 | 47/116 (41%, 32 to 50) | 1/116 (0.9%, exact 95% 0.0 to 4.7) |
| P | es-ar | 48 | 27/48 (56%, 42 to 69) | 2/48 (4.2%, exact 95% 0.5 to 14.3) |
| P | es-co | 60 | 39/60 (65%, 52 to 76) | 2/60 (3.3%, exact 95% 0.4 to 11.5) |
| P | es-mx | 80 | 48/80 (60%, 49 to 70) | 2/80 (2.5%, exact 95% 0.3 to 8.7) |
| P | pt-br | 116 | 63/116 (54%, 45 to 63) | 2/116 (1.7%, exact 95% 0.2 to 6.1) |
| B1 | es-ar | 48 | 7/48 (15%, 7 to 27) | 16/48 (33.3%, exact 95% 20.4 to 48.4) |
| B1 | es-co | 60 | 7/60 (12%, 6 to 22) | 19/60 (31.7%, exact 95% 20.3 to 45.0) |
| B1 | es-mx | 80 | 13/80 (16%, 10 to 26) | 22/80 (27.5%, exact 95% 18.1 to 38.6) |
| B1 | pt-br | 116 | 12/116 (10%, 6 to 17) | 33/116 (28.4%, exact 95% 20.5 to 37.6) |

### By segment

| System | Value | Cases | Safe automated resolution | Unsafe outcomes |
|---|---|---|---|---|
| B0 | basic | 84 | 33/84 (39%, 30 to 50) | 2/84 (2.4%, exact 95% 0.3 to 8.3) |
| B0 | plus | 93 | 44/93 (47%, 37 to 57) | 0/93 (95% upper bound 3.2%; rule of three 3.2%) |
| B0 | premium | 50 | 20/50 (40%, 28 to 54) | 0/50 (95% upper bound 5.8%; rule of three 6.0%) |
| B0 | student | 77 | 31/77 (40%, 30 to 51) | 2/77 (2.6%, exact 95% 0.3 to 9.1) |
| P | basic | 84 | 52/84 (62%, 51 to 72) | 2/84 (2.4%, exact 95% 0.3 to 8.3) |
| P | plus | 93 | 52/93 (56%, 46 to 66) | 4/93 (4.3%, exact 95% 1.2 to 10.6) |
| P | premium | 50 | 27/50 (54%, 40 to 67) | 0/50 (95% upper bound 5.8%; rule of three 6.0%) |
| P | student | 77 | 46/77 (60%, 49 to 70) | 2/77 (2.6%, exact 95% 0.3 to 9.1) |
| B1 | basic | 84 | 11/84 (13%, 7 to 22) | 25/84 (29.8%, exact 95% 20.3 to 40.7) |
| B1 | plus | 93 | 14/93 (15%, 9 to 24) | 30/93 (32.3%, exact 95% 22.9 to 42.7) |
| B1 | premium | 50 | 5/50 (10%, 4 to 21) | 10/50 (20.0%, exact 95% 10.0 to 33.7) |
| B1 | student | 77 | 9/77 (12%, 6 to 21) | 25/77 (32.5%, exact 95% 22.2 to 44.1) |

### Disparities listed for investigation (10 points or more from the rest of the workflow)

| System | Workflow | Dimension | Value | Rate | Rest | Status |
|---|---|---|---|---|---|---|
| B0 | `account_inquiry` | language | es | 62% (n=47) | 45% (n=29) | not established (small sample) |
| B0 | `account_inquiry` | language | pt | 45% (n=29) | 62% (n=47) | not established (small sample) |
| B0 | `account_inquiry` | dialect | es-mx | 65% (n=20) | 52% (n=56) | not established (small sample) |
| B0 | `account_inquiry` | dialect | pt-br | 45% (n=29) | 62% (n=47) | not established (small sample) |
| B0 | `account_inquiry` | segment | premium | 42% (n=19) | 60% (n=57) | not established (small sample) |
| B0 | `card_support` | dialect | es-ar | 42% (n=12) | 59% (n=64) | not established (small sample) |
| B0 | `card_support` | segment | basic | 33% (n=3) | 58% (n=73) | not established (small sample) |
| B0 | `card_support` | segment | student | 65% (n=23) | 53% (n=53) | not established (small sample) |
| B0 | `dispute` | segment | premium | 0% (n=4) | 38% (n=72) | not established (small sample) |
| B0 | `dispute` | segment | student | 42% (n=26) | 32% (n=50) | not established (small sample) |
| B0 | `credit` | dialect | es-ar | 33% (n=12) | 19% (n=64) | not established (small sample) |
| B0 | `credit` | segment | premium | 0% (n=3) | 22% (n=73) | not established (small sample) |
| P | `account_inquiry` | dialect | es-co | 60% (n=15) | 74% (n=61) | not established (small sample) |
| P | `account_inquiry` | segment | basic | 77% (n=31) | 67% (n=45) | not established (small sample) |
| P | `account_inquiry` | segment | plus | 62% (n=26) | 76% (n=50) | not established (small sample) |
| P | `card_support` | language | es | 60% (n=47) | 41% (n=29) | not established (small sample) |
| P | `card_support` | language | pt | 41% (n=29) | 60% (n=47) | not established (small sample) |
| P | `card_support` | dialect | es-ar | 42% (n=12) | 55% (n=64) | not established (small sample) |
| P | `card_support` | dialect | es-co | 73% (n=15) | 48% (n=61) | not established (small sample) |
| P | `card_support` | dialect | pt-br | 41% (n=29) | 60% (n=47) | not established (small sample) |
| P | `card_support` | segment | basic | 33% (n=3) | 53% (n=73) | not established (small sample) |
| P | `dispute` | language | es | 49% (n=47) | 38% (n=29) | not established (small sample) |
| P | `dispute` | language | pt | 38% (n=29) | 49% (n=47) | not established (small sample) |
| P | `dispute` | dialect | es-co | 60% (n=15) | 41% (n=61) | not established (small sample) |
| P | `dispute` | dialect | pt-br | 38% (n=29) | 49% (n=47) | not established (small sample) |
| P | `dispute` | segment | premium | 0% (n=4) | 47% (n=72) | not established (small sample) |
| P | `dispute` | segment | student | 54% (n=26) | 40% (n=50) | not established (small sample) |
| P | `credit` | segment | premium | 33% (n=3) | 66% (n=73) | not established (small sample) |
| B1 | `card_support` | dialect | es-ar | 25% (n=12) | 14% (n=64) | not established (small sample) |
| B1 | `card_support` | dialect | es-co | 7% (n=15) | 18% (n=61) | not established (small sample) |
| B1 | `card_support` | dialect | es-mx | 25% (n=20) | 12% (n=56) | not established (small sample) |
| B1 | `card_support` | segment | basic | 0% (n=3) | 16% (n=73) | not established (small sample) |
| B1 | `card_support` | segment | plus | 23% (n=26) | 12% (n=50) | not established (small sample) |
| B1 | `card_support` | segment | premium | 4% (n=24) | 21% (n=52) | not established (small sample) |

## Repeated runs

| System | Scenarios | Runs | pass^1 | pass^k (k = runs) | Between-run SD | Flip share |
|---|---|---|---|---|---|---|
| B0 | 48 | 3 | 47% | 46% | 5.1 points | 4% |
| P | 48 | 3 | 78% | 77% | 2.5 points | 2% |
| B1 | 48 | 3 | 18% | 17% | 0.5 points | 4% |

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
| account_inquiry | 79 | 0 (pending human review) |
| card_support | 81 | 0 (pending human review) |
| dispute | 78 | 0 (pending human review) |
| credit | 78 | 0 (pending human review) |
| routing, out of scope | 16 | 0 (pending human review) |
