"""Renders ``docs/evaluation/resolver.md`` from the evaluation JSON written by ``bank-ml resolver evaluate``.

Example texts are built from organizer transactions, so every digit in them is masked (``#``) before they enter the
committed report (CLAUDE.md rule 5 limits committed organizer data to the governed sample)."""

import re
from typing import Any

from bank_ml.common.reports import pct, table
from bank_ml.router.report import ci

USES = {
    "dispute": "Dispute (transactions in the dispute window)",
    "payment_lookup": "Payment lookup (payments and transfers)",
}
KEYS = ("top1", "mrr", "coverage", "wrong_rate", "wrong_among_auto", "correct_clarify", "absent_false_auto")
HEADER = ["Top-1", "MRR", "Coverage (auto)", "Wrong-transaction rate", "Wrong among auto", "Correct clarify"]
HEADER += ["Target absent, auto-selected", "n (queries / customers)"]


def _cells(summary: dict[str, Any]) -> list[str]:
    return [*(ci(summary[key], 3) for key in KEYS), f"{summary['queries']} / {summary['customers']}"]


def _mask(text: str) -> str:
    return re.sub(r"\d", "#", text).replace("|", "/")


def _headline(result: dict[str, Any], use: str) -> list[str]:
    rows = []
    for name, model in result["models"].items():
        rows.append([f"`{name}`, two or more candidates", *_cells(model["test"][use]["two_or_more_candidates"])])
        rows.append([f"`{name}`, all queries", *_cells(model["test"][use]["all"])])
    return table(["Model", *HEADER], rows)


def _slices(result: dict[str, Any], use: str, key: str, title: str) -> list[str]:
    names = list(result["models"])
    first = result["models"][names[0]]["test"][use][key]
    rows = []
    for position, row in enumerate(first):
        cells = [
            f"{ci(result['models'][n]['test'][use][key][position]['top1'], 2)} / "
            f"{ci(result['models'][n]['test'][use][key][position]['wrong_rate'], 3)}"
            for n in names
        ]
        rows.append([row["slice"], row["queries"], *cells])
    return table([title, "Queries", *(f"{n} top-1 / wrong rate" for n in names)], rows)


def _dev(result: dict[str, Any]) -> list[str]:
    keys = list(next(iter(result["models"].values()))["dev"])
    rows = [[f"`{name}`", *(f"{model['dev'][k]:.4f}" for k in keys)] for name, model in result["models"].items()]
    return table(["Model", *keys], rows)


def _silver(result: dict[str, Any]) -> list[str]:
    data = result["silver"]
    counts = data["counts"]
    verification = data["verification"]
    precision = (
        f"precision {pct(verification['precision'])} over {verification['verified']} verified items"
        if verification.get("status") == "verified"
        else f"precision **pending** (sheet {data['sheet']}, {verification.get('items', 0)} items, not yet verified)"
    )
    lines = [
        f"{counts['complaints_with_claimed_amount']:,} `Transactions` and `Fees` complaints carry a claimed amount; "
        f"{counts['with_any_match']:,} match at least one own transaction (same currency, amount within 1%, 60 days "
        f"before the complaint), {counts['unique_match']:,} exactly one. Silver-label {precision}. The sheet lives in "
        "`data/labeling/resolver_silver_sample.csv` (gitignored: organizer records). This is a secondary evaluation "
        "and partly circular: the descriptor carries the claimed amount that also defines the match.",
        "",
    ]
    rows = [[f"`{name}`", *_cells(summary)] for name, summary in data["models"].items()]
    return lines + table(["Model", *HEADER], rows)


def _failures(result: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for name, rows in result["failures"].items():
        lines += [f"### `{name}`", ""]
        if not rows:
            lines += ["No failures on test.", ""]
            continue
        lines += table(
            [
                "Description (digits masked)",
                "Use",
                "Candidates",
                "Target present",
                "Wrong auto-selection",
                "Target rank",
            ],
            [
                [
                    _mask(r["text"]),
                    r["use"],
                    r["candidates"],
                    r["target_present"],
                    r["auto_selected_wrong"],
                    r["target_rank"] or "not ranked",
                ]
                for r in rows
            ],
        )
        lines.append("")
    return lines


def render(result: dict[str, Any]) -> str:
    dataset = result["dataset"]
    margin = result.get("margin") or {}
    params = result.get("params") or {}
    lines = [
        "# Resolver evaluation",
        "",
        f"Generated {result['generated_at']} from commit `{result['git_sha']}` by `bank-ml resolver evaluate`. "
        "Do not edit by hand; rerun `make train` (or `bank-ml resolver evaluate`).",
        "",
        f"- Dataset `{dataset['version']}`, content hash `{dataset['hash'][:16]}`: "
        + ", ".join(f"{split} {count}" for split, count in dataset["rows_per_split"].items())
        + " queries; "
        + "; ".join(dataset["notes"])
        + ".",
        f"- Evaluated artifact ({result['alias']}): `{result['artifact']}`; clear-winner margin "
        f"{margin.get('threshold', 0):.4f}, chosen on dev for at most {pct(margin.get('target', 0))} wrong among "
        f"auto-selected (dev coverage {pct(margin.get('coverage', 0))}, dev wrong {pct(margin.get('risk', 0))}), "
        f"together with the none-of-these score {params.get('null_score', 0):.4f} so that at most 5.0% of dev "
        f"target-absent queries are auto-selected (dev: {pct(params.get('dev_absent_auto', 0))}).",
        "- Labels are by construction: each description was generated from a known gold transaction (synthetic "
        "organizer data) with deterministic es and pt templates. 10% of dev and test queries remove the target from "
        "the candidates; any auto-selection there is wrong. Intervals are 95% bootstraps resampling customers.",
        "- `rules@1` is evaluated at its shipped thresholds; `lgbm` at the dev-chosen margin. The test split was never "
        "used for any choice.",
        "",
    ]
    for use, title in USES.items():
        lines += [f"## {title} (test)", "", *_headline(result, use), ""]
        lines += ["By language:", "", *_slices(result, use, "by_language", "Language"), ""]
        lines += ["By country:", "", *_slices(result, use, "by_country", "Country"), ""]
        lines += ["By candidate count:", "", *_slices(result, use, "by_candidates", "Candidates"), ""]
        lines += ["By the amount clue given:", "", *_slices(result, use, "by_amount_clue", "Amount clue"), ""]
        lines += ["By the merchant clue given:", "", *_slices(result, use, "by_merchant_clue", "Merchant clue"), ""]
        lines += ["By the date clue given:", "", *_slices(result, use, "by_date_clue", "Date clue"), ""]
    lines += ["## Dev split (used for early stopping, the margin, and promotion)", "", *_dev(result), ""]
    lines += ["## Silver labels (secondary)", "", *_silver(result), ""]
    lines += ["## Failure examples (test)", "", *_failures(result)]
    return "\n".join(lines).rstrip() + "\n"
