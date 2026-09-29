# Judge rubric and human rating protocol

The language model judge (`evals/src/bank_evals/prompts/judge_transcript/1.md`, output `JudgeRating`) rates how the assistant writes in one conversation. It never decides task success, policy compliance, or safety: the deterministic graders decide those ([methodology](methodology.md#metric-definitions)). Its ratings are reported next to the outcome metrics, labeled as judge ratings, with the agreement against human ratings or "pending".

## Items

| Item | Scale | 5 (or true) | 3 | 1 (or false) |
|---|---|---|---|---|
| `language_correct` | true or false | Every assistant message is in the customer's language (Spanish for es locales, Brazilian Portuguese for pt-BR); quoted policy text in the right language is fine | | One Spanish sentence in a Portuguese conversation, or the reverse |
| `tone` | 1 to 5 | Calm, respectful, professional throughout | Acceptable but stiff or uneven | Rude, cold, or alarming |
| `clarity` | 1 to 5 | Every message says plainly what happened, what is next, and what the customer must do | Understandable with effort | Confusing or contradictory |
| `politeness` | 1 to 5 | Courteous without excess | Neutral | Impolite or dismissive |
| `language_quality` | 1 to 5 | Natural and correct for the locale (voseo in es-AR, Brazilian spelling in pt-BR) | Correct but awkward or of mixed register | Many errors or machine-like phrasing |

Rules for the judge and for human raters alike:

- Rate the assistant only, never the customer.
- Do not reward or punish what the assistant decided (an abstention, a transfer, a refusal); rate how it said it.
- A fixed policy excerpt appended to a reply counts toward clarity only when it confuses the answer.
- Model and settings: the run's model (the local `ollama/qwen2.5:7b-instruct` in session 14b), temperature 0, one call per transcript.

## Human rating protocol

1. `bank-eval judge reports/eval/<run_id> --llm replay --sample 100` writes `judge_sample.jsonl`: 100 transcripts spread round robin over systems (P, B1, B0), workflows, and languages, each ordered by a seeded hash, with the judge's rating and an empty `human` field.
2. Two raters per language (a native Spanish speaker for es and a native Portuguese speaker for pt) rate every transcript of their language independently, without looking at the judge's rating, filling `human` with the five items. Raters see the transcript only, never the scenario's expected outcome.
3. Disagreements between the two raters of a transcript (a different `language_correct`, or any scale differing by 2 or more) are adjudicated by a third person; the adjudicated rating is the human rating.
4. Copy the rated file to `evals/data/judge_ratings.<run_id>.jsonl`, record the raters and the date in `docs/PROGRESS.md`, and run `bank-eval judge reports/eval/<run_id> --ratings evals/data/judge_ratings.<run_id>.jsonl`.
5. Agreement: Cohen's kappa and percent agreement per item, with each 1 to 5 scale read as acceptable (4 or 5) or not. A kappa below 0.4 on an item means the judge's ratings on that item are not reported as evidence.

Status: pending human action (session 14b produces the sample; the ratings are a team task).
