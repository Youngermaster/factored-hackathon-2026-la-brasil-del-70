# Data use

What data the system holds, where it comes from, which fields leave the process for a language model provider, and why. The rules are CLAUDE.md rules 4 to 6 and the brief's "Data and execution boundaries" (`docs/organizer/BRIEF.md`).

## What the data is

- **All customer data is synthetic organizer data**: the organizer's synthetic banking delivery (customers in Mexico, Colombia, and Argentina, their products, transactions, complaints, credit profiles, call-center records). No real person's record is in the system.
- **Team-made fixtures**: test data (`services/api/tests/`, labeled as fixtures), evaluation scenarios (`evals/src/bank_evals/scenarios/`), the synthetic policy pack (`policies/`), the synthetic credit catalog and eligibility rules (labeled synthetic wherever they appear), and the two seeded demo records (one dispute case, one credit intake, labeled `seed`).
- **The committed sample** in `data_platform/sample/`: 2,595 rows of the organizer delivery across all tables (the bound is 5,000; a check in `make check` fails above it), chosen by a seeded hash of customers and followed through every table, with direct identifiers (document numbers, names, emails, phones, addresses, birth dates) replaced by deterministic, format-valid pseudonyms. Its README states the source, the dataset version, the extraction command and seed, and the per-table counts. The deployed demo is seeded from this sample only. The organizer's data-use terms were checked before the repository was made public: the human confirmed on 2026-09-30 that no restriction on redistributing the sample is known ([data/data-use.md](../data/data-use.md)).
- The full delivery (about 23.5 million rows) lives only under `data/` on team machines (gitignored) and is never deployed.

## What reaches a model provider

Only the variables a prompt declares reach a model (`services/api/src/bank_agent/prompts/<prompt_id>/<version>.md`, loaded by the prompt registry, which refuses undeclared variables). Every variable marked `untrusted` is wrapped in data delimiters and redacted first.

| Prompt | Variables sent | Why |
|---|---|---|
| `detect_escalation_signals` | the customer's latest message (redacted), the session locale | Detect a request for a person, distress, or a legal mention |
| `classify_intent_fallback` | the message (redacted), the router's candidate labels (no scores), the locale | Name the intent when the router is unsure |
| `extract_account_inquiry_slots`, `extract_dispute_slots` | the message (redacted), today's date, the locale | Read amounts, dates, merchants, and product hints from the text |
| `extract_card_support_slots`, `extract_credit_slots` | the message (redacted), the locale | The same for card and credit requests |
| `phrase_response` (off by default, `WORKFLOW_LLM_PHRASING`) | the workflow, the reply kind, verified facts as one-line strings (redacted), policy clause texts, the message for tone (redacted), the eligibility outcome code and its reasons (no values) | Phrase a reply that the grounding verifier then checks |
| `summarize_for_handoff` (off by default, `WORKFLOW_LLM_HANDOFF_SUMMARY`) | the request (redacted), verified facts (redacted), actions with their status, the escalation reason code, open questions (redacted) | A summary for the agent that may cite only the given facts |

Never sent, by construction: document numbers, full names, emails, phone numbers, addresses, customer or account identifiers, session tokens, the credit profile (score, income, utilization, days past due), the risk estimate (probability, interval, band), and the synthetic eligibility rules or their thresholds. The prompt registry refuses to load a prompt that declares such a variable, and the tests prove the credit paths:

- `services/api/tests/unit/adapters/test_prompt_registry.py::test_no_prompt_declares_a_variable_that_carries_internal_data` and `::test_phrase_response_allowlist_excludes_risk_score_income_and_arrears` (the phase 08 allowlist);
- `services/api/tests/integration/workflows/test_credit_separation.py::test_no_prompt_receives_a_profile_or_estimate_value_on_any_credit_path` and `::test_no_prompt_receives_a_learned_estimate_value`.

## Redaction

`adapters/llm/redaction.py` scrubs every variable outside a short allowlist of code-written keys before the request leaves the process: emails, Mexican CURP, Brazilian CPF and CNPJ, document numbers introduced by a keyword (CC, cédula, DNI, CPF, RG, documento, pasaporte), card numbers, phone numbers, dot-grouped numbers shaped like Argentine DNI or Colombian CC, long digit runs, the session's sensitive terms (for example the customer's first name), and names introduced by phrases such as "me llamo" or "meu nome é". Each match becomes a labeled marker such as `[EMAIL]`. Amounts next to a currency marker or word stay, because slot extraction needs them. Tests: `services/api/tests/unit/adapters/llm/test_redaction.py`. Logs have their own redaction processor (`bootstrap/logging.py`); telemetry carries ids and codes only (`docs/operations/observability.md`).

## Providers

| Configuration | Where prompts go |
|---|---|
| `LLM_PROVIDER=fake` (the default) | Nowhere: every model call is refused and the workflows use their deterministic paths |
| The local verification and the optional `ollama` profile (`ollama/qwen2.5:7b-instruct`) | A model on the same machine or the VM's private Docker network; nothing leaves the host |
| A hosted provider through LiteLLM (for example `openai/gpt-5-mini` or an Anthropic model) | The provider's API over https, with the operator's key; the only path where prompts leave the host |

Before switching to a hosted provider, the operator checks, for the account the key belongs to:

- that API inputs and outputs are **not used for training** (the default for the major providers' business APIs; confirm it in the account's data controls);
- the **retention period** of API logs kept for abuse monitoring, and whether a zero-data-retention option is available and wanted;
- the **processing region**, for the cross-border transfer rules noted in `docs/security/data-retention.md`;
- that the key is scoped to this project and has a spending limit at the provider, in addition to the service's own budget caps (`LLM_DAILY_BUDGET_USD`, per conversation and per session).

The deployment guide (`deploy/README.md`, "Choosing the model") lists the settings for each option.
