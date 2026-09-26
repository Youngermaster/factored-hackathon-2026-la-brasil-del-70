# bank_agent.prompts

## Responsibility

Versioned prompt files for every language model call. Code references a prompt by id and version (`PromptRef`, for example `extract_dispute_slots@1`), never by inline text and never as "latest", and every execution record stores the version it used. `FilePromptRegistry` (`bank_agent/adapters/prompts/file_registry.py`) loads the files once at startup and implements the `PromptRegistry` port.

## Prompts

| Prompt | Output | Used for |
|---|---|---|
| `extract_dispute_slots@1` | `DisputeSlotExtraction` | Intent candidates, the transaction as described, dispute reason candidates |
| `extract_account_inquiry_slots@1` | `AccountInquirySlotExtraction` | Product hint (type or last four digits), statement period expression, payment descriptor |
| `extract_card_support_slots@1` | `CardSupportSlotExtraction` | Card hint, requested `CardAction`, block reason candidates |
| `extract_credit_slots@1` | `CreditSlotExtraction` | Product of interest, amount, term, purpose, customer-declared monthly income; never an eligibility judgement |
| `classify_intent_fallback@1` | `IntentClassification` | Only when the learned router is uncertain; every intent plus `out_of_scope`; intents, never workflow decisions |
| `detect_escalation_signals@1` | `EscalationSignals` | Legal or regulator mention, distress, a request for a human, third-party admission |
| `phrase_response@1` | plain text | The customer-facing reply in Spanish or natural Brazilian Portuguese, from given facts and clause texts only |
| `summarize_for_handoff@1` | `HandoffSummaryDraft` | One paragraph for the agent, citing numbered verified facts; re-checked by the grounding verifier |

The output models live in `bank_agent/domain/llm_outputs.py`. Extraction fields have no defaults, so the model must write `null` explicitly for anything the customer did not say.

## File format

```text
prompts/
└── <prompt_id>/
    └── <version>.md        1.md, 2.md, ...
```

Each file is YAML front matter, then a `## System` section and a `## User` section:

| Front matter key | Meaning |
|---|---|
| `id` | Stable prompt id, equal to the directory name |
| `version` | Positive integer, equal to the file name without `.md` |
| `purpose` | One sentence on what the prompt is for |
| `owner` | The team or person who reviews changes |
| `inputs` | Each input variable with `type` (`str`, `int`, `bool`, `decimal`, `money`, `list_str`), `required` (default true), `untrusted` (default false), and `description` |
| `output_model` | A class name from `OUTPUT_MODELS`, or `null` for plain text |
| `changelog` | One entry per version: `version` and `change` |

Placeholders are written `{{ name }}` and must match the declared inputs exactly: an undeclared placeholder or an unused input fails loading.

## Rules the registry enforces

- **Only declared inputs.** Rendering raises `PromptVariablesError` on unknown, missing, or mistyped variables. The declared inputs are the prompt's allowlist: `phrase_response` can never receive a risk estimate, a credit score, an income, or days past due, because it does not declare them.
- **No internal data.** A prompt that declares an input whose name carries a risk estimate, a credit profile fact, or an internal flag (`forbidden_variable_reason` in `domain/llm_outputs.py`) fails to load.
- **Untrusted text is data.** Inputs marked `untrusted` are wrapped in `<data name="...">` and `</data>`; anything inside that looks like a delimiter is escaped, and a placeholder written by a customer is never expanded. The system message then ends with a fixed instruction that data is never instructions.
- **Language.** The gateway appends the session language to the system message. Portuguese replies must be natural Brazilian Portuguese, not translated Spanish; `phrase_response` states this and a cassette test checks it.
- **Published versions are immutable.** A change is a new version file with a changelog entry; callers move to it explicitly.

Redaction happens before rendering, in the gateway: every variable not in the redaction allowlist (`UNREDACTED_VARIABLE_KEYS` in `adapters/llm/redaction.py`) has emails, phone numbers, document numbers, card numbers, long digit runs, and names masked.

## How to add or change a prompt

1. Write `<prompt_id>/<version>.md` with complete front matter. For a change, copy the latest version to the next number and add a changelog entry; never edit a published version.
2. If it returns structured output, add the model to `domain/llm_outputs.py` and to `OUTPUT_MODELS`.
3. Mark every input that comes from a customer or a stored record as `untrusted: true`. Add an input to the redaction allowlist only when it can never contain personal data.
4. Reference it from code as `PromptRef(prompt_id=..., version=...)`.

## How to test

- `uv run pytest services/api/tests/unit/adapters/test_prompt_registry.py`: every shipped prompt loads, variable validation, delimiters, and the forbidden-variable check.
- Script the prompt in `FakeLLM` for workflow tests.
- Add cassettes in `evals/cassettes/<prompt_id>/<version>/` for es and pt, including an ambiguous and an out-of-scope message (see `evals/cassettes/README.md`). Until a provider and key are chosen, the cassettes are hand-authored fixtures.

## How to evaluate

Phase 14 compares prompt versions and models on the held-out workload with recorded cassettes, per workflow. A new version replaces the old one in code only after the evaluation shows it is at least as good on every workflow slice.
