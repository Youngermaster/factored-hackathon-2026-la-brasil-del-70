# 0015: Router model choice

- Status: accepted
- Date: 2026-09-27

## Context

The `IntentRouter` port needs a learned implementation that beats `router:keyword@1` across the four workflows and out of scope, in es-MX, es-CO, es-AR, and pt-BR. Three facts constrain the choice.

- **No usable labels in the delivery.** Transcripts hold 42 distinct balance-question texts, `detected_intents` is constant, and the mapped contact reason agrees with it 0% of the time. Training text must be team-authored seeds with provenance ([plan](../plans/phase-10a.md), [labeling protocol](../analysis/labeling-protocol.md)).
- **The API image has no ML libraries and must not gain them.** sentence-transformers lives only in the optional `ml` extra.
- **No language model provider is chosen**, so no model-based paraphrase or zero-shot reference can be run.

## Considered options

1. **Keep `router:keyword@1`.** It is transparent and has no training data dependency. On test it reaches 0.381 accuracy [0.299, 0.455], 0.385 macro-F1, and 0.471 mean high-stakes recall, and its errors among covered items run at 36%.
2. **TF-IDF (word and character n-grams) with logistic regression**, exported as JSON and evaluated in pure Python. Test: 0.677 accuracy [0.596, 0.749], 0.661 macro-F1, 0.827 workflow accuracy, and 0.741 mean high-stakes recall. It covers 48% of messages at its dev threshold and runs anywhere.
3. **multilingual-e5-small embeddings with logistic regression**, a JSON head plus the encoder from the `ml` extra. Test: 0.749 accuracy [0.679, 0.805], 0.742 macro-F1, 0.834 workflow accuracy, 0.805 mean high-stakes recall, 62% coverage at its dev threshold, and the best calibration (ECE 0.072). It needs the extra, which the API image does not have.
4. **A language model classifier** (`classify_intent_fallback@1`). It cannot be measured without a provider, and it would put a model call on every turn.

## Decision

- **Build and register both 2 and 3** behind the port. Both are promoted as champions on dev macro-F1 with high-stakes recall and workflow accuracy guards.
- **Embeddings are the better model;** TF-IDF is the one that runs in the current API image. For a deployment that can install the `ml` extra, `WORKFLOW_ROUTER=embeddings@champion`; otherwise `tfidf@champion`.
- **The default stays `router:keyword@1`** until phase 14 runs the scenario and evaluation sets end to end with a learned router, because the learned models were measured only on team-written text.
- **Artifacts are JSON parameters** with the analyzer and embedder recorded, loaded through the filesystem `ModelRegistry` with a digest check. Pickled scikit-learn objects are never loaded.
- **Thresholds, temperatures, C, and promotion all use dev.** The test split is reported only.

## Consequences

- Training and serving share one analyzer (`text_features.router_terms`) and the same adapter, so what is evaluated is what serves.
- The out-of-scope class is weak for every model (embeddings 0.281, TF-IDF 0.031 on test). The in-domain unsupported recognizers (ADR 0025) and the out-of-scope answer remain the safety net, and more `unsupported` seeds are the first data to add.
- The test error among covered items (about 10%) is twice the dev target of 5%; dev has 68 seed groups. Human labels, native pt review, and generated paraphrases (all pending) are the next inputs, followed by retraining and re-choosing the threshold.
- Serving embeddings requires the `ml` extra (806 MB). Where it is absent, the composition root falls back to the keyword baseline and logs the reason.
