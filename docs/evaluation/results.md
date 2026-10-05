# Evaluation results: hosted test run (test split, azure/gpt-4.1-mini)

Generated 2026-10-05T18:51:03+00:00 from commit `2ddabb0f`; run `test-hosted` on the test split (`scenarios.test.jsonl`, SHA-256 `292c7c0b17c3f04d`), 332 scenarios, 3 run(s), language model mode `record`, cassette misses 0, harness errors 0.

Systems and model labels: B0 (menu and rules bot): `none`, P (proposed system): `azure/gpt-4.1-mini (litellm)`, B1 (naive LLM agent): `azure/gpt-4.1-mini (litellm)`.

**Measurement label: simulated, offline.** Scripted and model-played customers on a synthetic evaluation world; not a production measurement. Projected figures are labeled projected.

## `account_inquiry`

| Metric | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| Cases (in scope) | 76 | 76 | 76 |
| Safe automated resolution | 45/76 (59%, 48 to 70) | 32/76 (42%, 32 to 53) | 44/76 (58%, 47 to 68) |
| Automation attempted | 63/76 (83%, 73 to 90) | 72/76 (95%, 87 to 98) | 62/76 (82%, 71 to 89) |
| Containment | 59/76 (78%, 67 to 86) | 70/76 (92%, 84 to 96) | 60/76 (79%, 69 to 87) |
| Missed transfers | 0/14 (0%, 0 to 22) | 8/14 (57%, 33 to 79) | 2/14 (14%, 4 to 40) |
| Unnecessary transfers | 3/62 (5%, 2 to 13) | 0/62 (0%, 0 to 6) | 4/62 (6%, 3 to 15) |
| Handoff completeness | 14/14 (100%, 78 to 100) | 4/6 (67%, 30 to 90) | 12/12 (100%, 76 to 100) |
| Unsafe outcomes | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 16/76 (21.1%, exact 95% 12.5 to 31.9) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| Task success | 59/76 (78%, 67 to 86) | 43/76 (57%, 45 to 67) | 56/76 (74%, 63 to 82) |
| Policy compliance | 76/76 (100%, 95 to 100) | 76/76 (100%, 95 to 100) | 76/76 (100%, 95 to 100) |
| Routing correct | 62/76 (82%, 71 to 89) | 0/0 (not defined) | 66/76 (87%, 77 to 93) |
| Language correct | 47/76 (62%, 51 to 72) | 76/76 (100%, 95 to 100) | 74/76 (97%, 91 to 99) |
| Latency per turn p50 / p95 | 51 ms / 138 ms | 2767 ms / 14191 ms | 1630 ms / 11553 ms |
| Cost per attempted case | 0.000000 USD | 0.001643 USD | 0.001109 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.003697 USD | 0.001562 USD |

| Unsafe outcome type | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| credit approval claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| false success claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| forbidden disclosure | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 2/76 (2.6%, exact 95% 0.3 to 9.2) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| materially incorrect | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 12/76 (15.8%, exact 95% 8.4 to 26.0) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| unauthorized action | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 4/76 (5.3%, exact 95% 1.5 to 12.9) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |

## `card_support`

| Metric | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| Cases (in scope) | 76 | 76 | 76 |
| Safe automated resolution | 47/76 (62%, 51 to 72) | 26/76 (34%, 25 to 45) | 48/76 (63%, 52 to 73) |
| Automation attempted | 68/76 (89%, 81 to 95) | 75/76 (99%, 93 to 100) | 67/76 (88%, 79 to 94) |
| Containment | 62/76 (82%, 71 to 89) | 74/76 (97%, 91 to 99) | 57/76 (75%, 64 to 83) |
| Missed transfers | 3/17 (18%, 6 to 41) | 16/17 (94%, 73 to 99) | 3/17 (18%, 6 to 41) |
| Unnecessary transfers | 0/59 (0%, 0 to 6) | 1/59 (2%, 0 to 9) | 5/59 (8%, 4 to 18) |
| Handoff completeness | 14/14 (100%, 78 to 100) | 0/1 (0%, 0 to 79) | 14/14 (100%, 78 to 100) |
| Unsafe outcomes | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 7/76 (9.2%, exact 95% 3.8 to 18.1) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| Task success | 61/76 (80%, 70 to 88) | 38/76 (50%, 39 to 61) | 62/76 (82%, 71 to 89) |
| Policy compliance | 76/76 (100%, 95 to 100) | 60/76 (79%, 69 to 87) | 76/76 (100%, 95 to 100) |
| Routing correct | 71/76 (93%, 86 to 97) | 0/0 (not defined) | 71/76 (93%, 86 to 97) |
| Language correct | 47/76 (62%, 51 to 72) | 76/76 (100%, 95 to 100) | 75/76 (99%, 93 to 100) |
| Latency per turn p50 / p95 | 12 ms / 50 ms | 2417 ms / 5033 ms | 1520 ms / 3735 ms |
| Cost per attempted case | 0.000000 USD | 0.001996 USD | 0.001111 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.005759 USD | 0.001550 USD |

| Unsafe outcome type | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| credit approval claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| false success claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 2/76 (2.6%, exact 95% 0.3 to 9.2) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| forbidden disclosure | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 3/76 (3.9%, exact 95% 0.8 to 11.1) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| materially incorrect | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| unauthorized action | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 2/76 (2.6%, exact 95% 0.3 to 9.2) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |

## `dispute`

| Metric | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| Cases (in scope) | 76 | 76 | 76 |
| Safe automated resolution | 29/76 (38%, 28 to 49) | 3/76 (4%, 1 to 11) | 45/76 (59%, 48 to 70) |
| Automation attempted | 65/76 (86%, 76 to 92) | 73/76 (96%, 89 to 99) | 68/76 (89%, 81 to 95) |
| Containment | 57/76 (75%, 64 to 83) | 66/76 (87%, 77 to 93) | 59/76 (78%, 67 to 86) |
| Missed transfers | 2/14 (14%, 4 to 40) | 11/14 (79%, 52 to 92) | 0/14 (0%, 0 to 22) |
| Unnecessary transfers | 7/62 (11%, 6 to 22) | 7/62 (11%, 6 to 22) | 3/62 (5%, 2 to 13) |
| Handoff completeness | 12/12 (100%, 76 to 100) | 1/3 (33%, 6 to 79) | 14/14 (100%, 78 to 100) |
| Unsafe outcomes | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 13/76 (17.1%, exact 95% 9.4 to 27.5) | 1/76 (1.3%, exact 95% 0.0 to 7.1) |
| Task success | 41/76 (54%, 43 to 65) | 21/76 (28%, 19 to 39) | 60/76 (79%, 69 to 87) |
| Policy compliance | 76/76 (100%, 95 to 100) | 38/76 (50%, 39 to 61) | 76/76 (100%, 95 to 100) |
| Routing correct | 62/76 (82%, 71 to 89) | 0/0 (not defined) | 73/76 (96%, 89 to 99) |
| Language correct | 47/76 (62%, 51 to 72) | 76/76 (100%, 95 to 100) | 75/76 (99%, 93 to 100) |
| Latency per turn p50 / p95 | 23 ms / 49 ms | 2848 ms / 7431 ms | 1373 ms / 6984 ms |
| Cost per attempted case | 0.000000 USD | 0.002929 USD | 0.001744 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.071272 USD | 0.002636 USD |

| Unsafe outcome type | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| credit approval claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| false success claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 1/76 (1.3%, exact 95% 0.0 to 7.1) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| forbidden disclosure | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 5/76 (6.6%, exact 95% 2.2 to 14.7) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| materially incorrect | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| unauthorized action | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 7/76 (9.2%, exact 95% 3.8 to 18.1) | 1/76 (1.3%, exact 95% 0.0 to 7.1) |

## `credit`

| Metric | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| Cases (in scope) | 76 | 76 | 76 |
| Safe automated resolution | 20/76 (26%, 18 to 37) | 8/76 (11%, 5 to 19) | 48/76 (63%, 52 to 73) |
| Automation attempted | 31/76 (41%, 30 to 52) | 76/76 (100%, 95 to 100) | 73/76 (96%, 89 to 99) |
| Containment | 31/76 (41%, 30 to 52) | 70/76 (92%, 84 to 96) | 58/76 (76%, 66 to 84) |
| Missed transfers | 4/19 (21%, 9 to 43) | 14/19 (74%, 51 to 88) | 2/19 (11%, 3 to 31) |
| Unnecessary transfers | 30/57 (53%, 40 to 65) | 1/57 (2%, 0 to 9) | 1/57 (2%, 0 to 9) |
| Handoff completeness | 7/15 (47%, 25 to 70) | 5/5 (100%, 57 to 100) | 17/17 (100%, 82 to 100) |
| Unsafe outcomes | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 56/76 (73.7%, exact 95% 62.3 to 83.1) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| Task success | 23/76 (30%, 21 to 41) | 20/76 (26%, 18 to 37) | 64/76 (84%, 74 to 91) |
| Policy compliance | 35/76 (46%, 35 to 57) | 42/76 (55%, 44 to 66) | 66/76 (87%, 77 to 93) |
| Routing correct | 73/76 (96%, 89 to 99) | 0/0 (not defined) | 70/76 (92%, 84 to 96) |
| Language correct | 47/76 (62%, 51 to 72) | 76/76 (100%, 95 to 100) | 73/76 (96%, 89 to 99) |
| Latency per turn p50 / p95 | 9 ms / 29 ms | 3365 ms / 6004 ms | 1944 ms / 15790 ms |
| Cost per attempted case | 0.000000 USD | 0.002719 USD | 0.001288 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.025827 USD | 0.001959 USD |

| Unsafe outcome type | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| credit approval claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 28/76 (36.8%, exact 95% 26.1 to 48.7) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| false success claim | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| forbidden disclosure | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 49/76 (64.5%, exact 95% 52.7 to 75.1) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| materially incorrect | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 26/76 (34.2%, exact 95% 23.7 to 46.0) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |
| unauthorized action | 0/76 (95% upper bound 3.9%; rule of three 3.9%) | 26/76 (34.2%, exact 95% 23.7 to 46.0) | 0/76 (95% upper bound 3.9%; rule of three 3.9%) |

## Aggregate (the four workflows, never read alone)

| Metric | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| Cases (in scope) | 304 | 304 | 304 |
| Safe automated resolution | 141/304 (46%, 41 to 52) | 69/304 (23%, 18 to 28) | 185/304 (61%, 55 to 66) |
| Automation attempted | 227/304 (75%, 69 to 79) | 296/304 (97%, 95 to 99) | 270/304 (89%, 85 to 92) |
| Containment | 209/304 (69%, 63 to 74) | 280/304 (92%, 89 to 95) | 234/304 (77%, 72 to 81) |
| Missed transfers | 9/64 (14%, 8 to 25) | 49/64 (77%, 65 to 85) | 7/64 (11%, 5 to 21) |
| Unnecessary transfers | 40/240 (17%, 12 to 22) | 9/240 (4%, 2 to 7) | 13/240 (5%, 3 to 9) |
| Handoff completeness | 47/55 (85%, 74 to 92) | 10/15 (67%, 42 to 85) | 57/57 (100%, 94 to 100) |
| Unsafe outcomes | 0/304 (95% upper bound 1.0%; rule of three 1.0%) | 92/304 (30.3%, exact 95% 25.1 to 35.8) | 1/304 (0.3%, exact 95% 0.0 to 1.8) |
| Task success | 184/304 (61%, 55 to 66) | 122/304 (40%, 35 to 46) | 242/304 (80%, 75 to 84) |
| Policy compliance | 263/304 (87%, 82 to 90) | 216/304 (71%, 66 to 76) | 294/304 (97%, 94 to 98) |
| Routing correct | 268/304 (88%, 84 to 91) | 0/0 (not defined) | 280/304 (92%, 89 to 95) |
| Language correct | 188/304 (62%, 56 to 67) | 304/304 (100%, 99 to 100) | 297/304 (98%, 95 to 99) |
| Latency per turn p50 / p95 | 17 ms / 74 ms | 2904 ms / 7330 ms | 1630 ms / 8526 ms |
| Cost per attempted case | 0.000000 USD | 0.002326 USD | 0.001318 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.009978 USD | 0.001923 USD |

| Unsafe outcome type | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| credit approval claim | 0/304 (95% upper bound 1.0%; rule of three 1.0%) | 28/304 (9.2%, exact 95% 6.2 to 13.0) | 0/304 (95% upper bound 1.0%; rule of three 1.0%) |
| false success claim | 0/304 (95% upper bound 1.0%; rule of three 1.0%) | 3/304 (1.0%, exact 95% 0.2 to 2.9) | 0/304 (95% upper bound 1.0%; rule of three 1.0%) |
| forbidden disclosure | 0/304 (95% upper bound 1.0%; rule of three 1.0%) | 59/304 (19.4%, exact 95% 15.1 to 24.3) | 0/304 (95% upper bound 1.0%; rule of three 1.0%) |
| materially incorrect | 0/304 (95% upper bound 1.0%; rule of three 1.0%) | 38/304 (12.5%, exact 95% 9.0 to 16.8) | 0/304 (95% upper bound 1.0%; rule of three 1.0%) |
| unauthorized action | 0/304 (95% upper bound 1.0%; rule of three 1.0%) | 39/304 (12.8%, exact 95% 9.3 to 17.1) | 1/304 (0.3%, exact 95% 0.0 to 1.8) |

## Routing scenarios (switches and requests out of every workflow)

| Metric | B0 (menu and rules bot) | B1 (naive LLM agent) | P (proposed system) |
|---|---|---|---|
| Cases (in scope) | 28 (small) | 28 (small) | 28 (small) |
| Safe automated resolution | 9/12 (75%, 47 to 91) | 5/12 (42%, 19 to 68) | 12/12 (100%, 76 to 100) |
| Automation attempted | 12/12 (100%, 76 to 100) | 12/12 (100%, 76 to 100) | 12/12 (100%, 76 to 100) |
| Containment | 12/12 (100%, 76 to 100) | 12/12 (100%, 76 to 100) | 12/12 (100%, 76 to 100) |
| Missed transfers | 0/0 (not defined) | 0/0 (not defined) | 0/0 (not defined) |
| Unnecessary transfers | 2/28 (7%, 2 to 23) | 1/28 (4%, 1 to 18) | 3/28 (11%, 4 to 27) |
| Handoff completeness | 0/0 (not defined) | 0/0 (not defined) | 0/0 (not defined) |
| Unsafe outcomes | 3/28 (10.7%, exact 95% 2.3 to 28.2) | 2/28 (7.1%, exact 95% 0.9 to 23.5) | 0/28 (95% upper bound 10.1%; rule of three 10.7%) |
| Task success | 14/28 (50%, 33 to 67) | 17/28 (61%, 42 to 76) | 17/28 (61%, 42 to 76) |
| Policy compliance | 28/28 (100%, 88 to 100) | 21/28 (75%, 57 to 87) | 28/28 (100%, 88 to 100) |
| Routing correct | 19/28 (68%, 49 to 82) | 0/0 (not defined) | 24/28 (86%, 69 to 94) |
| Language correct | 17/28 (61%, 42 to 76) | 28/28 (100%, 88 to 100) | 26/28 (93%, 77 to 98) |
| Latency per turn p50 / p95 | 10 ms / 18 ms | 2563 ms / 4562 ms | 1129 ms / 3632 ms |
| Cost per attempted case | 0.000000 USD | 0.005684 USD | 0.002664 USD |
| Cost per safe automated resolution | 0.000000 USD | 0.013642 USD | 0.002664 USD |

## Slices (safe automated resolution and unsafe outcomes)

### By language

| System | Value | Cases | Safe automated resolution | Unsafe outcomes |
|---|---|---|---|---|
| B0 | es | 188 | 91/188 (48%, 41 to 56) | 0/188 (95% upper bound 1.6%; rule of three 1.6%) |
| B0 | pt | 116 | 50/116 (43%, 34 to 52) | 0/116 (95% upper bound 2.5%; rule of three 2.6%) |
| P | es | 188 | 115/188 (61%, 54 to 68) | 1/188 (0.5%, exact 95% 0.0 to 2.9) |
| P | pt | 116 | 70/116 (60%, 51 to 69) | 0/116 (95% upper bound 2.5%; rule of three 2.6%) |
| B1 | es | 188 | 45/188 (24%, 18 to 31) | 56/188 (29.8%, exact 95% 23.4 to 36.9) |
| B1 | pt | 116 | 24/116 (21%, 14 to 29) | 36/116 (31.0%, exact 95% 22.8 to 40.3) |

### By dialect

| System | Value | Cases | Safe automated resolution | Unsafe outcomes |
|---|---|---|---|---|
| B0 | es-ar | 48 | 21/48 (44%, 31 to 58) | 0/48 (95% upper bound 6.1%; rule of three 6.2%) |
| B0 | es-co | 60 | 29/60 (48%, 36 to 61) | 0/60 (95% upper bound 4.9%; rule of three 5.0%) |
| B0 | es-mx | 80 | 41/80 (51%, 40 to 62) | 0/80 (95% upper bound 3.7%; rule of three 3.8%) |
| B0 | pt-br | 116 | 50/116 (43%, 34 to 52) | 0/116 (95% upper bound 2.5%; rule of three 2.6%) |
| P | es-ar | 48 | 28/48 (58%, 44 to 71) | 0/48 (95% upper bound 6.1%; rule of three 6.2%) |
| P | es-co | 60 | 40/60 (67%, 54 to 77) | 0/60 (95% upper bound 4.9%; rule of three 5.0%) |
| P | es-mx | 80 | 47/80 (59%, 48 to 69) | 1/80 (1.2%, exact 95% 0.0 to 6.8) |
| P | pt-br | 116 | 70/116 (60%, 51 to 69) | 0/116 (95% upper bound 2.5%; rule of three 2.6%) |
| B1 | es-ar | 48 | 9/48 (19%, 10 to 32) | 11/48 (22.9%, exact 95% 12.0 to 37.3) |
| B1 | es-co | 60 | 14/60 (23%, 14 to 35) | 19/60 (31.7%, exact 95% 20.3 to 45.0) |
| B1 | es-mx | 80 | 22/80 (28%, 19 to 38) | 26/80 (32.5%, exact 95% 22.4 to 43.9) |
| B1 | pt-br | 116 | 24/116 (21%, 14 to 29) | 36/116 (31.0%, exact 95% 22.8 to 40.3) |

### By segment

| System | Value | Cases | Safe automated resolution | Unsafe outcomes |
|---|---|---|---|---|
| B0 | basic | 84 | 38/84 (45%, 35 to 56) | 0/84 (95% upper bound 3.5%; rule of three 3.6%) |
| B0 | plus | 93 | 48/93 (52%, 42 to 62) | 0/93 (95% upper bound 3.2%; rule of three 3.2%) |
| B0 | premium | 50 | 21/50 (42%, 29 to 56) | 0/50 (95% upper bound 5.8%; rule of three 6.0%) |
| B0 | student | 77 | 34/77 (44%, 34 to 55) | 0/77 (95% upper bound 3.8%; rule of three 3.9%) |
| P | basic | 84 | 50/84 (60%, 49 to 69) | 0/84 (95% upper bound 3.5%; rule of three 3.6%) |
| P | plus | 93 | 61/93 (66%, 55 to 74) | 0/93 (95% upper bound 3.2%; rule of three 3.2%) |
| P | premium | 50 | 26/50 (52%, 39 to 65) | 0/50 (95% upper bound 5.8%; rule of three 6.0%) |
| P | student | 77 | 48/77 (62%, 51 to 72) | 1/77 (1.3%, exact 95% 0.0 to 7.0) |
| B1 | basic | 84 | 21/84 (25%, 17 to 35) | 28/84 (33.3%, exact 95% 23.4 to 44.5) |
| B1 | plus | 93 | 22/93 (24%, 16 to 33) | 25/93 (26.9%, exact 95% 18.2 to 37.1) |
| B1 | premium | 50 | 14/50 (28%, 17 to 42) | 12/50 (24.0%, exact 95% 13.1 to 38.2) |
| B1 | student | 77 | 12/77 (16%, 9 to 25) | 27/77 (35.1%, exact 95% 24.5 to 46.8) |

### Disparities listed for investigation (10 points or more from the rest of the workflow)

| System | Workflow | Dimension | Value | Rate | Rest | Status |
|---|---|---|---|---|---|---|
| B0 | `account_inquiry` | language | es | 64% (n=47) | 52% (n=29) | not established (small sample) |
| B0 | `account_inquiry` | language | pt | 52% (n=29) | 64% (n=47) | not established (small sample) |
| B0 | `account_inquiry` | dialect | es-ar | 50% (n=12) | 61% (n=64) | not established (small sample) |
| B0 | `account_inquiry` | dialect | es-mx | 75% (n=20) | 54% (n=56) | not established (small sample) |
| B0 | `account_inquiry` | dialect | pt-br | 52% (n=29) | 64% (n=47) | not established (small sample) |
| B0 | `account_inquiry` | segment | premium | 42% (n=19) | 65% (n=57) | not established (small sample) |
| B0 | `card_support` | dialect | es-ar | 50% (n=12) | 64% (n=64) | not established (small sample) |
| B0 | `card_support` | segment | basic | 33% (n=3) | 63% (n=73) | not established (small sample) |
| B0 | `card_support` | segment | premium | 54% (n=24) | 65% (n=52) | not established (small sample) |
| B0 | `card_support` | segment | student | 70% (n=23) | 58% (n=53) | not established (small sample) |
| B0 | `dispute` | segment | premium | 0% (n=4) | 40% (n=72) | not established (small sample) |
| B0 | `dispute` | segment | student | 46% (n=26) | 34% (n=50) | not established (small sample) |
| B0 | `credit` | dialect | es-ar | 42% (n=12) | 23% (n=64) | not established (small sample) |
| B0 | `credit` | segment | plus | 35% (n=20) | 23% (n=56) | not established (small sample) |
| B0 | `credit` | segment | premium | 0% (n=3) | 27% (n=73) | not established (small sample) |
| P | `account_inquiry` | language | es | 51% (n=47) | 69% (n=29) | not established (small sample) |
| P | `account_inquiry` | language | pt | 69% (n=29) | 51% (n=47) | not established (small sample) |
| P | `account_inquiry` | dialect | es-mx | 50% (n=20) | 61% (n=56) | not established (small sample) |
| P | `account_inquiry` | dialect | pt-br | 69% (n=29) | 51% (n=47) | not established (small sample) |
| P | `card_support` | dialect | es-ar | 42% (n=12) | 67% (n=64) | not established (small sample) |
| P | `card_support` | dialect | es-co | 80% (n=15) | 59% (n=61) | not established (small sample) |
| P | `card_support` | segment | basic | 33% (n=3) | 64% (n=73) | not established (small sample) |
| P | `dispute` | language | es | 64% (n=47) | 52% (n=29) | not established (small sample) |
| P | `dispute` | language | pt | 52% (n=29) | 64% (n=47) | not established (small sample) |
| P | `dispute` | dialect | es-co | 73% (n=15) | 56% (n=61) | not established (small sample) |
| P | `dispute` | dialect | pt-br | 52% (n=29) | 64% (n=47) | not established (small sample) |
| P | `dispute` | segment | basic | 68% (n=25) | 55% (n=51) | not established (small sample) |
| P | `dispute` | segment | premium | 0% (n=4) | 62% (n=72) | supported |
| P | `credit` | dialect | es-ar | 75% (n=12) | 61% (n=64) | not established (small sample) |
| P | `credit` | segment | basic | 56% (n=25) | 67% (n=51) | not established (small sample) |
| P | `credit` | segment | plus | 75% (n=20) | 59% (n=56) | not established (small sample) |
| P | `credit` | segment | premium | 33% (n=3) | 64% (n=73) | not established (small sample) |
| B1 | `account_inquiry` | dialect | es-ar | 33% (n=12) | 44% (n=64) | not established (small sample) |
| B1 | `account_inquiry` | dialect | es-mx | 50% (n=20) | 39% (n=56) | not established (small sample) |
| B1 | `account_inquiry` | segment | basic | 52% (n=31) | 36% (n=45) | not established (small sample) |
| B1 | `account_inquiry` | segment | plus | 35% (n=26) | 46% (n=50) | not established (small sample) |
| B1 | `card_support` | language | es | 38% (n=47) | 28% (n=29) | not established (small sample) |
| B1 | `card_support` | language | pt | 28% (n=29) | 38% (n=47) | not established (small sample) |
| B1 | `card_support` | dialect | es-ar | 25% (n=12) | 36% (n=64) | not established (small sample) |
| B1 | `card_support` | dialect | es-mx | 45% (n=20) | 30% (n=56) | not established (small sample) |
| B1 | `card_support` | dialect | pt-br | 28% (n=29) | 38% (n=47) | not established (small sample) |
| B1 | `card_support` | segment | basic | 0% (n=3) | 36% (n=73) | not established (small sample) |
| B1 | `card_support` | segment | plus | 42% (n=26) | 30% (n=50) | not established (small sample) |
| B1 | `credit` | segment | premium | 0% (n=3) | 11% (n=73) | not established (small sample) |

## Repeated runs

| System | Scenarios | Runs | pass^1 | pass^k (k = runs) | Between-run SD | Flip share |
|---|---|---|---|---|---|---|
| B0 | 48 | 3 | 52% | 52% | 4.4 points | 0% |
| P | 48 | 3 | 80% | 77% | 2.2 points | 4% |
| B1 | 48 | 3 | 43% | 33% | 2.1 points | 19% |

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
