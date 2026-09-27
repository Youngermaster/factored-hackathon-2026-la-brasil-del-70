# Synthetic policy pack

**Everything in this directory is synthetic demonstration content written by the team for the Factored AI & Data Hackathon 2026 prototype. It is not a real regulation, not legal advice, and not the terms, policies, products, or credit criteria of any real bank.** Values are chosen to be plausible for Mexico, Colombia, and Argentina and are labeled `synthetic: true` in every file.

The pack is the single source of both the deterministic rules' parameters and the customer-facing explanations, so the two cannot disagree. The kernel that enforces it lives in `services/api/src/bank_agent/policy/` ([package README](../services/api/src/bank_agent/policy/README.md)); the generated overview of every clause, rule, binding, and product is [`docs/policy/catalog.md`](../docs/policy/catalog.md).

## Layout

| Path | Content |
|---|---|
| `pack.yaml` | Pack id, label, supported workflows, languages |
| `clauses/<family>/<CLAUSE-ID>.<lang>.md` | One file per clause per language (`es`, `pt`, `en`) |
| `clauses/<family>/superseded/<CLAUSE-ID>@<version>.<lang>.md` | Superseded versions, kept so old execution records stay resolvable (none yet) |
| `bindings.yaml` | Clauses common to every state, then workflow, state, required authentication, and bound clauses |
| `matrix.yaml` | One row per write action: confirmation, base authentication level, step-up, allowed states per workflow |
| `messages/eligibility.<lang>.yaml` | Sentences of the customer-facing eligibility explanation |
| `credit/<PRODUCT-CODE>.yaml` | The synthetic credit catalog: one product per jurisdiction per file, with es, pt, and en display text |
| `versions.lock.yaml` | Generated: each clause's version and a digest of its three language files |

## Clause format

A clause file is YAML front matter between `---` lines, validated by `ClauseMetadata` (schema `contracts/schemas/policy_clause.v1.json`), then the customer-facing body:

```markdown
---
clause_id: DSP-CO-1
version: 1
jurisdiction: CO
language: es
effective_from: 2026-09-27
synthetic: true
params:
  dispute_window_days: 60
bound_rules: [DSP.within_window]
summary: Plazo sintético para presentar una reclamación por una transacción en Colombia.
---
En Colombia puedes presentar una reclamación ... dentro de los {dispute_window_days} días calendario ...
```

- `clause_id` is `FAMILY-JURISDICTION-NUMBER`, with the jurisdiction `MX`, `CO`, `AR`, or `ALL`; the family decides the folder.
- `params` are integers, booleans, short strings, lists of strings, or amounts written as `{amount: "10000.00", currency: MXN}` (never floats).
- `bound_rules` names the rule ids that read this clause. A rule's parameters are the merged parameters of every clause of the customer's jurisdiction (or `ALL`) that binds it, and those clauses are its citations.
- A `{param}` placeholder may name only an integer, string, or amount parameter of the same clause; a code list is written out in prose instead.
- The three language twins must have the same id, version, jurisdiction, effective date, parameters, bound rules, and placeholders.
- ELG clauses declare `product_type` (`credit_card` or `personal_loan`); exactly one per jurisdiction and type.
- Credit clauses (CRE, ELG), the eligibility messages, and every rendered credit text contain no approval wording in any language, even negated (see `bank_agent/policy/lexicon.py`).

## Families

| Family | Covers |
|---|---|
| SCOPE | Supported and unsupported requests |
| AUTH | Identity per action; a document number never proves identity |
| PRV | Disclosure, masking, third-party requests |
| ACC | Balances and payments with the as-of statement, the statement period cap, unsupported account requests |
| CRD | Card status, the protective block with step-up and its consequences, unblock and replacement handed to a human |
| DSP | Dispute window, SLA, and automatic intake limit per country; eligible statuses, required information, reasons, duplicates, ownership |
| ESC | Escalation criteria, handoff SLA per country, distress and vulnerability, credit review |
| INF | What happens next after a case, a block, or an application intake |
| CRE | The indicative disclaimer, catalog information, unsupported credit requests, rate disclosure basis per country |
| ELG | The synthetic eligibility rules per jurisdiction and product type |

## How to add or change a clause

1. Edit (or add) the `es`, `pt`, and `en` files together. Keep parameters, bound rules, and placeholders identical.
2. If the clause already existed, raise `version` by one in all three files. To keep the old text resolvable, move the previous files to `superseded/<CLAUSE-ID>@<old version>.<lang>.md` first.
3. If the clause binds a new rule, add the pure rule function in `bank_agent/policy/rules/`, with tests, and bind the clause to the states that need it in `bindings.yaml`.
4. Run `make policy-lock` (it refuses a changed clause that kept its version), then `make policy-catalog`.
5. Run the policy tests: `uv run pytest services/api/tests/unit/policy services/api/tests/integration/policy`. Golden texts change only with a reviewed wording change (see `test_policy_golden.py`).

## Review workflow

Every clause change goes through a pull request reviewed by a Spanish speaker and a Portuguese speaker for plausibility and bilingual quality, workflow by workflow; the ELG thresholds and the credit catalog are reviewed separately. Reviewers and dates are recorded in `docs/PROGRESS.md`. The first human review of this pack is pending (see the phase 06 entry there).

## Versioning

- **Clause versions** only grow: `versions.lock.yaml` records each clause's version and content digest, and a pack whose content changed without a higher version fails to load.
- **Pack version**: `pack-` plus 16 hex digits of a SHA-256 over every file in this directory except this README. It is stored in every `Decision`, every eligibility assessment (`eligibility:synthetic@<pack version>`), and every execution record.
- **Catalog version**: `catalog_version` in every product file (`synthetic-catalog-2026.09.1`); change it with any product change.
