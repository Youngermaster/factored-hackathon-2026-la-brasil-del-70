# Model card: intent router

| Field | Value |
|---|---|
| Component | `IntentRouter` port (`bank_agent.ports.models`) |
| Implementations | `router:tfidf` (champion `986872f0284f`), `router:embeddings` (champion `32666d7d4e3f`); baselines `router:keyword@1` (served by default) and a majority class |
| Owner | ml |
| Trained by | `make train` (`bank-ml router train`); evaluated by `bank-ml router evaluate`; promoted by `make promote APPROVED_BY=...` |
| Full results | [`docs/evaluation/router.md`](../evaluation/router.md) (generated); hosted language model reference in [`docs/evaluation/router-llm.md`](../evaluation/router-llm.md) (generated, with a hand-written decision) |
| Decision record | [ADR 0015](../adr/0015-router-model-choice.md) |

## Intended use

Classify one customer chat message, in Spanish (Mexico, Colombia, Argentina) or Brazilian Portuguese, into one of the 17 `Intent` values, so the workflow engine can dispatch it to `account_inquiry`, `card_support`, `dispute`, or `credit`, answer a shared intent (`informational`, `human_request`, `greeting_or_other`), or treat it as out of scope (`unsupported`). Below the artifact's threshold the prediction is marked `below_threshold`, and the engine asks which of the two likely workflows the customer means. The router only proposes an intent; the policy kernel, state machines, and verified tools decide everything else.

Out of scope: any decision, any language other than es and pt, multi-intent messages (one label per message), and voice input (only simulated speech-to-text noise was tested).

## Data

- **No organizer text.** Transcripts carry no intent signal: 147,292 interactions have customer text, but there are only 42 distinct texts (balance-question templates), and `detected_intents` is `consulta_general` or null. The mapped contact reason agrees with `detected_intents` 0% of the time (`docs/analysis/labeling-protocol.md`, and the last section of the evaluation).
- **Team-authored seeds.** 544 seeds (8 per intent and locale: es-MX, es-CO, es-AR, pt-BR) in `ml/corpus/router/seeds/`, with slots filled from `ml/corpus/router/lexicon.yaml`. `unsupported` seeds are half unsupported banking requests and half off-domain text. The pt-BR seeds await native review.
- **Deterministic augmentation** (seeded per seed): slot substitution, regional slang, keyboard typos, casing and punctuation noise, dropped accents. Each item is labeled `team_authored` (the canonical fill) or `augmented_from:<seed_id>`. There are 2,351 items: 544 team-authored, 544 typo, 518 casing, 413 accent, 263 slot, and 69 slang items.
- **Language-model paraphrases:** designed and built (`paraphrase_router_seed@1` for training and a different `paraphrase_router_eval@1` for the evaluation set) but not generated. No provider has been chosen, and no cassette was fabricated. This is a pending human action.

## Splits and leakage prevention

- Seeds whose canonical texts are near-duplicates (MinHash LSH, confirmed by exact Jaccard of at least 0.6 on character 4-grams) share one seed group. This includes two cross-intent minimal pairs ("bloquear" against "desbloquear", balance against statement), which stay in one split.
- Groups are split per intent and locale: 2 test, 1 dev, 5 train of 8. All augmentations follow their group. The result is train 1,464 items, dev 286 items (68 groups), and test 601 items (136 groups).
- Dev and test items within Jaccard 0.8 of a train item would be removed; none were.
- A unit test (`ml/tests/unit/router/test_corpus_guard.py`) builds the dataset from the committed corpus and fails on a seed group in two splits, an exact normalized duplicate across splits, or a cross-split pair at or above 0.8 (exact scan).
- The test split was never used for any choice. C, the temperature, the abstention threshold, and promotion all use dev.

## Models

| Model | Features | Head | Chosen on dev |
|---|---|---|---|
| `router:tfidf` | Shared analyzer `router_terms@1`: folded words, word bigrams, and character 2- to 5-grams; digits masked; sublinear TF-IDF; 15,366 terms | Multinomial logistic regression | C = 100 by macro-F1; temperature 0.60; threshold 0.884 |
| `router:embeddings` | `intfloat/multilingual-e5-small` query embeddings (`ml` extra) | Multinomial logistic regression | C = 500; temperature 0.90; threshold 0.801 |
| `router:keyword@1` | Weighted regular expressions (phase 09) | Best pattern weight | Fixed threshold 0.6 |
| Majority | None | Most frequent train intent | None |

Artifacts are JSON parameters, evaluated in pure Python inside `bank_agent`. The API image gains no ML library, nothing is unpickled, and the registry checks a SHA-256 digest before parsing. Evaluation loads the registered artifacts through the same adapters the API uses.

## Metrics (test split, 601 items in 136 seed groups, 95% seed-group bootstrap intervals)

This table is the phase 08 measurement, which the deck quotes so that `keyword@1` and the learned routers come from one run (`keyword@1` macro-F1 0.385). The 2026-10-05 re-measurement in the next section reports `keyword@1` at 0.395 on the same 601 items; [router-llm](../evaluation/router-llm.md) uses that later figure.

| Model | Accuracy | Macro-F1 | Workflow accuracy | Coverage at threshold | Error among covered | ECE | High-stakes recall (mean) |
|---|---|---|---|---|---|---|---|
| Majority | 0.075 [0.031, 0.128] | 0.008 | 0.136 | 1.000 | 0.925 | 0.007 | 0.167 |
| `keyword@1` | 0.381 [0.299, 0.455] | 0.385 [0.299, 0.439] | 0.574 [0.503, 0.656] | 0.491 | 0.363 [0.255, 0.484] | 0.185 | 0.471 |
| `tfidf` | 0.677 [0.596, 0.749] | 0.661 [0.575, 0.718] | 0.827 [0.761, 0.885] | 0.484 | 0.096 [0.034, 0.175] | 0.125 | 0.741 |
| `embeddings` | 0.749 [0.679, 0.805] | 0.742 [0.665, 0.796] | 0.834 [0.784, 0.884] | 0.619 | 0.102 [0.047, 0.161] | 0.072 | 0.805 |

- **High-stakes recall** covers the intents that lead to a write, a protective action, or a handoff: `dispute_new`, `card_block`, `card_unblock_request`, `card_replacement_request`, `credit_application`, and `human_request`. A miss there skips something the customer needed, so these recalls are reported next to macro-F1 and guard promotion. Embeddings reach 0.68 to 0.89 per intent; `card_unblock_request` and `human_request` are the weakest at 0.68 each. Keyword reaches 0.15 for `credit_application` and 0.24 for `human_request`.
- **Threshold target.** Intent error of at most 5% among covered items on dev. On test the error among covered items is about 10% for both learned models, twice the dev target, with wide intervals: dev has 68 seed groups. The threshold should be re-chosen once more dev data exists.
- **Slices (embeddings).** es 0.747, pt 0.755. es-MX 0.701, es-CO 0.778, es-AR 0.763, pt-BR 0.755. By workflow: account_inquiry 0.694, card_support 0.812, dispute 0.756, credit 0.833, shared 0.729, and **out_of_scope 0.281**. Out-of-scope text is the weakest slice for every model, and TF-IDF reaches only 0.031 there: off-domain and unsupported requests are diverse, and 8 seeds per locale do not cover them.
- **Robustness (canonical test seeds, 137 per set; embeddings, with TF-IDF in parentheses).** Clean 0.77 (0.67), dropped accents 0.78 (0.67), homophones 0.77 (0.67), fillers 0.72 (0.69), truncation to 60% of the words 0.53 (0.53), combined transcript style 0.73 (0.69).
- **Transfer (TF-IDF, same C).** pt-BR test accuracy is 0.63 when trained with Portuguese and 0.59 when trained on Spanish only, so the gap is small because character n-grams carry over. Held-out Spanish dialects score no worse than in distribution (es-MX 0.73 against 0.63, es-CO 0.81 against 0.73, es-AR 0.76 against 0.73), all within the intervals. This synthetic corpus shows no measurable dialect gap.

## Hosted language model reference (2026-10-05)

ADR 0015 option 4, a language model classifier, is now measured. The full results are in [`docs/evaluation/router-llm.md`](../evaluation/router-llm.md), and the decision rule was pre-registered in [`docs/plans/router-llm.md`](../plans/router-llm.md).

**Setup.**

- The model runs `classify_intent_fallback@1` zero-shot, at temperature 0, through the full gateway, so the message is redacted as in production.
- The models are `azure/gpt-4.1-mini` and `azure/gpt-4o`, and the calls are recorded as cassettes in `ml/cassettes/router_llm/`.
- It is compared with `keyword@1`, `tfidf@986872f0284f` (retrained from the committed seeds; it reproduces the registered version exactly), and cascades. In a cascade the classical router acts first, and the model is called only below that router's threshold.
- Thresholds were chosen on dev. Test numbers carry 95% seed-group bootstrap intervals.

| Test (601 items) | Macro-F1 | Accuracy | Confident write-intent misroutes | Out-of-scope messages confidently routed into a workflow (of 32) | Cost per 1,000 messages (list price) | p95 per message |
|---|---|---|---|---|---|---|
| `keyword@1` (served; re-measured 2026-10-05) | 0.395 [0.308, 0.447] | 0.393 | 33 | 0 | 0 | under 1 ms |
| `tfidf@986872f0284f` | 0.661 [0.575, 0.713] | 0.677 | 1 | 0 | 0 | under 10 ms |
| `gpt-4.1-mini` zero-shot | 0.885 [0.819, 0.925] | 0.889 | 31 | 13 | 0.42 USD | 2.4 s |
| `gpt-4o` zero-shot | 0.936 [0.890, 0.969] | 0.937 | 23 | 7 | 3.17 USD | 1.9 s |
| TF-IDF then `gpt-4.1-mini` | 0.873 [0.802, 0.918] | 0.879 | 11 | 7 | 0.22 USD | 1.7 s |
| TF-IDF then `gpt-4o` | 0.910 [0.857, 0.948] | 0.913 | 11 | 7 | 1.64 USD | 1.7 s |

These are offline measurements on synthetic text. The latency is the recorded provider round trip from the development machine.

**What they show.**

- The hosted model understands far more requests, especially in Portuguese (pt accuracy 0.90 to 0.92, against 0.63 for TF-IDF) and on the long-tail credit and status intents.
- It also guesses where the classical routers abstain. It confidently starts the wrong write flow far more often than TF-IDF, and it sends out-of-scope messages into workflows.
- The cascade keeps TF-IDF where TF-IDF is reliable (0.904 accuracy on the 48% of messages it acts on) and spends the model only where TF-IDF abstains (0.465 against 0.855 to 0.923).

**Decision.**

- Under the pre-registered dev rule, neither cascade qualifies for an end-to-end trial. The `gpt-4.1-mini` cascade made 2 confident write-intent misroutes on dev against a limit of 1, and the `gpt-4o` cascade costs 1.89 USD per 1,000 messages against a limit of 1.00.
- Production keeps `keyword@1`.
- The next steps are in the [backlog](../BACKLOG.md): a prompt version with intent definitions chosen on dev, a human audit of the label audit candidates, and, only if a cascade then passes the rule, a default-off flag with an end-to-end dev run.

## Limitations

- Every utterance was written or derived by the team (one author pool, which also wrote the keyword baseline), so accuracy on real customers will differ. Human validation of 200 items (`docs/evaluation/router-labeling.md`) and native review of pt-BR are pending.
- Dev and test are small (68 and 136 seed groups), so intervals are wide and the test error at the dev threshold exceeds the dev target.
- The out-of-scope class is weak; the in-domain unsupported recognizers (ADR 0029) and the out-of-scope answer remain the safety net.
- No language-model paraphrase was generated. The zero-shot reference ran on 2026-10-05 (section above), on the same synthetic text, so it shares every data limitation listed here.
- The embedding router needs the `ml` extra, which the API image does not install; without it the composition root serves the keyword baseline and logs the fallback.

## Ethical considerations

The router sees only message text and a language code, never identifiers. A misroute can send a protective request to the wrong workflow, so the engine confirms switches mid-flow, asks when the router is uncertain, and every write still needs confirmation, step-up, and verification. Portuguese and dialect performance are reported separately so a weaker group is visible. The default stays on `router:keyword@1`: session 14b measured `tfidf@champion` with the learned resolver end to end on the dev split with the local model and found no gain beyond noise (75 against 74 of 112, overlapping intervals; [results](../evaluation/results.md#decision-the-learned-router-resolver-and-risk-estimator-defaults-dev-evidence-only)). `WORKFLOW_ROUTER=embeddings@champion` or `tfidf@champion` switches them on.
