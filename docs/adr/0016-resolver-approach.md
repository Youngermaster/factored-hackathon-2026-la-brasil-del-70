# 0016: Resolver approach

- Status: accepted
- Date: 2026-09-27

## Context

The `TransactionResolver` port ranks the session customer's own transactions against a descriptor (amount, merchant words, dates, channel) that UNDERSTAND extracts from the message. Two uses need it: locating a charge to dispute and locating a payment or transfer whose status the customer asks about. The delivery has no complaint-to-transaction key; only 12 of 8,523 complaints with a claimed amount match any own transaction, so real labels do not exist. The API image has no ML libraries. A wrong auto-selection can lead to a dispute on the wrong charge, even though the confirmation step shows the transaction first.

## Considered options

1. **Keep `resolver:rules@1`.** Transparent and already at 0.989 top-1 on synthetic descriptions, but it auto-selects only 77 to 79% of queries with two or more candidates, so the rest get a clarifying question. It also auto-selects 4.9% of dispute queries whose true transaction is not among the candidates.
2. **A learned pointwise classifier** (for example logistic regression per candidate). It scores candidates independently, so it cannot learn relative evidence ("closest amount among these") without hand-built rank features, and it gives no natural per-query margin.
3. **A LightGBM lambdarank ranker** over shared, explicit features, with labels by construction from gold. It learns per-query ordering, handles non-linear interactions between amount, date, and merchant evidence, and exports to plain trees.
4. **A language model that picks the transaction.** No provider exists, candidate records would have to be sent to it, and the choice would be neither deterministic nor verifiable.

## Decision

Option 3, as `resolver:lgbm`:

- **Labels by construction.** Queries are generated from known gold transactions, with customer group and temporal splits and 10% target-absent queries in dev and test. Descriptors are produced by the engine's own understanding code, and the dataset hash covers them.
- **An evidence gate and a "none of these" option.** A candidate is ranked only if it agrees with at least one clue. The softmax includes a none option, and a clear winner must beat both the runner-up and the none option by a margin. The none score and the margin are chosen together on dev for maximum coverage, with at most 2% wrong among auto-selected queries and at most 5% auto-selection on target-absent queries. The first version, without the none option, auto-selected 24% of target-absent test queries; that is why it exists.
- **Plain trees in a JSON artifact**, served by a pure-Python evaluator in `bank_agent` that matches LightGBM to 1e-9 (tested). Early stopping and promotion use dev.
- **The default stays `resolver:rules@1`** until phase 14 measures the learned resolver end to end.

## Consequences

- On test (queries with two or more candidates), `resolver:lgbm` auto-selects 91.3% (dispute) and 93.6% (payment lookup) against 79.3% and 76.9% for rules. Its wrong-transaction rate is 0.000 and 0.001 against 0.003 and 0.000, and top-1 is 1.000 in both uses. The main gain is fewer clarifying questions at an equal or lower error.
- The synthetic task is near the ceiling for both models, so these numbers overstate real performance. Template descriptions, small candidate sets, and 24 merchant names make it easy.
- Silver labels from complaints cannot evaluate the resolver in this delivery (12 matches). The measured rate feeds the dispute data support item (BACKLOG) once the 12 are verified.
- The error analysis found an engine bug: an amount after a named date was read as its year. It was fixed in `application/understanding` with regression tests.
