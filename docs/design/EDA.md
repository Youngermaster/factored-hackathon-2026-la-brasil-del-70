# Local EDA viewer design

Audience: the hackathon team reviewing data quality and workflow feasibility.

Use Streamlit's native accessible controls, a warm off-white canvas, charcoal text and a muted
green chart accent. Tables carry the evidence. Avoid decorative graphics, animation and custom
HTML. Phase navigation and a persistent run selector keep provenance visible.

Each phase must work before later phases exist. Empty and failed phases have explicit states.
Demand filters apply to demand; global text diagnostics are labeled separately. English and Spanish
interface labels live together in the `TEXT` catalog. Metric identifiers and the report remain in
the repository's technical English.

Navigation has two sections. **Proceso EDA** retains the five sequential phase views. **Laboratorio**
contains table exploration, the relationship map and workflow decisions. Laboratory pages require
completed curation and analysis, but never start or modify a pipeline run.

The table explorer combines aggregate profiles with deterministic samples of 25, 50 or 100 rows.
Sample fields use a fail-closed allowlist: entity IDs become stable hash references, reviewed
low-cardinality categories remain, dates are reduced to month, and only a few technical flags are
shown. Free text, direct personal data, personal characteristics, fine-grained locations, financial
values and outcome labels are excluded. New contract fields stay out until reviewed. There is no
SQL input. DuckDB opens in read-only mode and the only record-level download is the sanitized sample.
If the warehouse is absent, the aggregate parts remain available. Hash references are pseudonyms,
not anonymized identifiers.

Relationship edges encode evidence: green means complete matching with no semantic mismatch,
yellow means at least 95 percent matching, red means lower coverage or inconsistent identity, and
gray means no observable foreign keys. Solid edges represent required keys and dashed edges are
optional. Selecting an edge exposes its denominators, matched and unmatched counts,
join row counts, fanout and identity mismatches.

The decision page compares data availability, join integrity, demand evidence, evaluation readiness
and policy safety. Each traffic light includes its evidence. It does not combine dimensions into a
score because a safety failure cannot be compensated by higher demand. The page reflects the current
project steering and does not change the chosen workflow; a change requires an explicit team decision.

The UI follows the restrained palette and spacing guidance of the repository's minimalist-ui
skill. The landing-page-specific design-taste-frontend rules do not apply to this data viewer.
