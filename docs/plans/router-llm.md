# Router benchmark: classical routers against a hosted language model (zero-shot and cascade)

Final-day track (2026-10-05). It closes the BACKLOG row "LLM-classifier reference for the router" and ADR 0015 option 4, which said the language model classifier "cannot be measured without a provider". Azure OpenAI is now available for offline evaluation, so it can be measured.

This file was committed **before any language model call was made and before any test number existed**. Provenance note: the commit that first recorded this file was lost to local disk corruption before it was pushed, and the file was restored unchanged from the working tree, so the git history alone cannot show that it predates the calls. The cassette timestamps (`recorded_at`) are the remaining evidence of when the calls were made. It pre-registers the questions, the systems, the metrics, and the decision rule. The generated report `docs/evaluation/router-llm.md` repeats the rule verbatim and evaluates it on dev mechanically.

## Questions

1. **Reference (report only).** On the frozen router test split (601 items, 136 seed groups), how does a hosted model used zero-shot compare with `keyword@1` (served today) and the TF-IDF champion `router:tfidf@986872f0284f`? The comparison covers accuracy, macro-F1, routing to the right workflow, abstention, safety, slices, latency, and cost.
2. **Decision.** Is a cascade worth an end-to-end trial? In the cascade, TF-IDF routes first and the model is called only below TF-IDF's abstention threshold (0.8838, chosen on dev at training). A trial means a default-off flag plus a `bank-eval` dev run.

## Systems

| System | What it is | Model calls |
|---|---|---|
| `keyword@1` | The served rule baseline, threshold 0.6 fixed in code | none |
| `tfidf@986872f0284f` | The champion, retrained from the committed seeds; it reproduces the registered version byte for byte | none |
| `llm:<model>` zero-shot | `classify_intent_fallback@1` with no router candidates, temperature 0, at most 200 output tokens, called through the full gateway (redaction, budget, tracing, retry), so the message is redacted exactly as in production | every message |
| `tfidf -> llm:<model>` cascade | TF-IDF where it is at or above its threshold, the model elsewhere | messages below the TF-IDF threshold |
| `keyword -> llm:<model>` cascade | The same with `keyword@1` first, as a reference for the served router (not part of the decision) | messages below 0.6 |

The models are `azure/gpt-4.1-mini`, called on the evaluation account at concurrency 8, and `azure/gpt-4o`, called on the production account at concurrency 2 with a request rate cap, because that account is shared with the live demo's fallback.

Label mapping: the prompt's `out_of_scope` and `unsupported` both map to `Intent.UNSUPPORTED`, the router's out-of-scope class. The model's top label is the prediction, and its stated confidence for that label is the confidence.

A call that still fails after retries, or returns output that fails validation after the gateway's one repair, is an **abstention**. It is scored as `unsupported` with confidence 0, below threshold, so the conversation would get a clarifying question. Failures are counted and reported per model and are never dropped.

## Data and splits

- Dataset `router-v1`, content hash `5ec099abd371...`: 1,464 train, 286 dev (68 seed groups), and 601 test items (136 seed groups). The text is synthetic: team-authored es-MX, es-CO, es-AR, and pt-BR seeds with deterministic augmentation.
- **Dev** is used for every choice:
  - the model's abstention threshold (`choose_threshold`, target error among covered at most 5%, the same rule as the learned routers);
  - the cascade's threshold for the model part (chosen on the dev items that reach the model);
  - the model choice;
  - the decision below.
- **Test** is used only to report the fixed configurations.

## Metrics

Each metric has a 95% percentile interval from the seed-group cluster bootstrap (1,000 resamples) where the existing evaluation code provides one:

- accuracy, macro-F1 over the 17 intents, and workflow accuracy;
- coverage, and error among covered items at the dev-chosen threshold;
- high-stakes recall, per intent and as a mean;
- the out-of-scope slice;
- by language (es, pt) and by dialect (locale);
- workflow confusion by language;
- confident misroutes into the write intents (`dispute_new`, `card_block`, `credit_application`): covered, wrong, and predicted as one of them;
- calibration of the model's stated confidence (ECE and reliability bins);
- latency p50 and p95 per message (the recorded latency of each model call; classical routers timed in process);
- tokens per call, and cost per 1,000 messages, from the measured tokens and the verified Azure retail list prices in `services/api/config/llm_prices.yaml`;
- failure and repair counts.

Labels: all numbers are **offline measurements** on synthetic text. Cost per 1,000 messages is measured tokens times list price. Any volume-based figure is **projected** and labeled so.

## Pre-registered decision rule

The language model zero-shot router is a **reference**, not a serving candidate. It sends every message to a hosted provider, and that has cost, latency, and data-flow consequences.

A cascade `tfidf -> llm:<model>` is **recommended for a default-off end-to-end dev trial** only if every criterion holds on **dev**:

1. Its macro-F1 exceeds TF-IDF alone by more than 0.05, and the 95% lower bound of the paired seed-group bootstrap difference is above 0.
2. Its high-stakes recall mean is not more than 0.02 below TF-IDF alone (the promotion guard tolerance).
3. Its confident misroutes into the write intents number at most TF-IDF's count plus 1.
4. The model is called on at most 60% of dev messages.
5. The p95 latency of the model call is at most 2,000 ms. The turn latency alert fires at a 5-second p95, and slot extraction already calls the model.
6. The cost is at most 1.00 USD per 1,000 messages at list price.

When both models qualify, the higher dev cascade macro-F1 wins. If the paired difference between the two cascades has a 95% interval that contains 0, the cheaper model (`azure/gpt-4.1-mini`) wins.

Test numbers never change the decision. If test disagrees with dev (for example, the test gain's interval contains 0), the report says so, and the decision stands until new dev evidence exists.

**No production default changes in this track, whatever the outcome.** The team's rule (`docs/evaluation/results.md`, "Decision: the learned router, resolver, and risk estimator defaults") changes a default only on a non-overlapping end-to-end dev gain. Production keeps `keyword@1`. A positive recommendation becomes a BACKLOG row for the flagged trial.

## Files

- `ml/src/bank_ml/router/zero_shot.py`: the classification calls (bounded concurrency, rate cap, retry with backoff on 429), the label mapping, the systems, and the metrics.
- `ml/src/bank_ml/router/zero_shot_report.py`: renders the report. The hand-written decision section is kept between markers when the report is regenerated.
- `ml/src/bank_ml/router/command.py`: `bank-ml router zero-shot`.
- `ml/cassettes/router_llm/`: the recorded calls, redacted, about 1 KB each. The repository already commits evaluation cassettes, so the report regenerates offline without a key.
- `services/api/config/llm_prices.yaml`: `azure/gpt-4.1-mini` and `azure/gpt-4o` at the verified Azure retail prices.
- `ml/tests/unit/router/test_zero_shot.py`: tests with a fake model client and no live calls.
- Docs:
  - `docs/evaluation/router-llm.md`;
  - `docs/models/router.md`;
  - `docs/adr/0015-router-model-choice.md` (notes only);
  - `ml/README.md`;
  - `docs/BACKLOG.md`;
  - `docs/PROGRESS.md`;
  - `docs/evaluation/router.md`, regenerated only if its keyword numbers are stale.

## Risks

- **Verbalized confidence is coarse.** Values such as 0.9, 0.95, and 1.0 make the dev threshold coarse, and the report says so.
- **The gpt-4o account is shared with the production fallback.** The requests are capped at about 35 per minute, roughly 30K of the 50K tokens per minute.
- **The labels follow the team's own protocol.** The prompt gives label names without definitions, so a zero-shot model cannot know conventions such as `informational` against `credit_product_info`. Its errors partly measure label ambiguity, and the report lists the high-confidence disagreements as candidates for the human label audit.
- **Dev is small** (68 seed groups), so the intervals are wide.
