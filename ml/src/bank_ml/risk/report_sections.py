"""Report sections for ``docs/evaluation/risk-estimator.md``: calibration, uncertainty, disparities, and errors."""

from collections.abc import Callable
from typing import Any

from bank_ml.common.reports import pct, table
from bank_ml.risk.slices import AUC_THRESHOLD, GAP_THRESHOLD, LOW_BAND_RATIO, SMALL_CUSTOMERS, SMALL_POSITIVES

LEARNED = ("logreg", "lgbm")
DIMENSION_TITLES = {
    "country": "Country",
    "segment": "Segment (slice only, never a feature)",
    "income_band": "Income band (within-country tertile)",
    "credit_products": "Credit product count (diagnostic; the main feature)",
}


def calibration(result: dict[str, Any], names: dict[str, str]) -> list[str]:
    lines = [
        "## Calibration",
        "",
        "Calibrators were fitted on the dev calibration half and chosen by log loss on the dev selection half.",
        "",
    ]
    rows = []
    for kind in LEARNED:
        learned = result["learned"][kind]
        losses = learned["calibration_selection_log_loss"]
        rows.append(
            [
                names[kind],
                f"`{learned['params']['calibrator']}`",
                *(f"{losses[k]:.4f}" for k in ("identity", "platt", "isotonic")),
            ]
        )
    lines += table(["Model", "Chosen", "Identity", "Platt", "Isotonic"], rows)
    for kind in LEARNED:
        bins = [b for b in result["models"][kind]["reliability"] if b["count"]]
        axis = ", ".join(f'"{b["lower"]:.1f}"' for b in bins)
        lines += [
            "",
            f"### Reliability, {names[kind]}",
            "",
            "```mermaid",
            "xychart-beta",
            f'    title "Reliability, {kind} (bars: observed rate; line: mean estimate)"',
            f"    x-axis [{axis}]",
            '    y-axis "Rate" 0 --> 1',
            "    bar [" + ", ".join(f"{b['observed']:.3f}" for b in bins) + "]",
            "    line [" + ", ".join(f"{b['mean_estimate']:.3f}" for b in bins) + "]",
            "```",
            "",
        ]
        lines += table(
            ["Bin", "Customers", "Mean estimate", "Observed rate"],
            [
                [
                    f"{b['lower']:.1f} to {b['upper']:.1f}",
                    b["count"],
                    f"{b['mean_estimate']:.3f}",
                    f"{b['observed']:.3f}",
                ]
                for b in bins
            ],
        )
    return [*lines, ""]


def uncertainty(result: dict[str, Any], names: dict[str, str], ci: Callable[..., str]) -> list[str]:
    lines = [
        "## Uncertainty intervals",
        "",
        "Two candidates per model, chosen on the dev selection half: a bootstrap ensemble (20 members refit on "
        "train bootstraps and recalibrated on dev bootstraps; 2.5% to 97.5% percentiles) and binned inductive "
        "Venn-Abers. Group coverage: ten equal-count groups by estimate; a group is covered when its mean "
        "interval intersects the 95% Wilson interval of its observed rate. The narrower method with coverage of "
        'at least 0.9 wins. "Inside" is the stricter share of customers in groups whose observed rate lies '
        "inside the mean interval.",
        "",
    ]
    rows = []
    for kind in LEARNED:
        choice = result["learned"][kind]["interval_choice"]
        for method, summary in choice["candidates"].items():
            chosen = "yes" if method == choice["chosen"] else ""
            rows.append(
                [
                    names[kind],
                    method,
                    f"{summary['group_coverage']:.2f}",
                    f"{summary['inside_share']:.2f}",
                    f"{summary['mean_width']:.4f}",
                    chosen,
                ]
            )
    lines += table(["Model", "Method (dev)", "Group coverage", "Inside", "Mean width", "Chosen"], rows)
    lines += ["", "Test coverage of the served intervals (all models; the baselines use their own intervals):", ""]
    test_rows = []
    for name, model in result["models"].items():
        cover = model["interval_coverage"]
        test_rows.append(
            [
                names[name],
                f"{cover['group_coverage']:.2f}",
                f"{cover['inside_share']:.2f}",
                f"{cover['mean_width']:.4f}",
            ]
        )
    lines += table(["Model", "Group coverage", "Inside", "Mean width"], test_rows)
    flag_rows = [
        [
            names[k],
            *(
                pct(result["learned"][k]["flags"][f])
                for f in ("missing_features", "out_of_distribution", "wide_interval")
            ),
        ]
        for k in LEARNED
    ]
    lines += ["", "Flags on test (share of customers):", ""]
    lines += table(["Model", "Missing features", "Out of distribution", "Wide interval (over 0.10)"], flag_rows)
    return [*lines, ""]


def disparities(result: dict[str, Any], names: dict[str, str], ci: Callable[..., str]) -> list[str]:
    lines = [
        "## Slices and disparities (test)",
        "",
        "**This is a disparity report for investigation, not a fairness certification.** Segment and country "
        "are never features. A group is listed when, against the rest of the population, its calibration gap "
        f"(mean estimate minus observed rate) differs by more than {GAP_THRESHOLD} with an interval excluding "
        f"zero, its ROC AUC differs by more than {AUC_THRESHOLD}, or its low-band share ratio is below "
        f"{LOW_BAND_RATIO}. Cells under {SMALL_CUSTOMERS} customers or {SMALL_POSITIVES} positives are flagged "
        "small and never listed.",
        "",
    ]
    listed = []
    for kind in LEARNED:
        lines += [f"### {names[kind]}", ""]
        for dimension, entries in result["models"][kind]["slices"].items():
            lines += [f"#### {DIMENSION_TITLES[dimension]}", ""]
            rows = []
            for e in entries:
                rows.append(
                    [
                        e["group"],
                        f"{e['customers']:,}",
                        e["positives"],
                        f"{e['prevalence']:.3f}",
                        f"{e['mean_estimate']:.3f}",
                        ci(e["gap"]),
                        ci(e["gap_vs_rest"]),
                        ci(e["roc_auc"]),
                        pct(e["low_band_share"]),
                        pct(e["borderline_share"]),
                        "small" if e["small_cell"] else "",
                        ", ".join(e["reasons"]) or "none",
                    ]
                )
                if e["listed"]:
                    listed.append(f"{names[kind]}, {dimension} `{e['group']}`: {', '.join(e['reasons'])}")
            lines += table(
                [
                    "Group",
                    "Customers",
                    "Positives",
                    "Prevalence",
                    "Mean estimate",
                    "Gap",
                    "Gap vs rest",
                    "ROC AUC",
                    "Low band",
                    "Borderline",
                    "Cell",
                    "Above a threshold",
                ],
                rows,
            )
            lines += [""]
    lines += ["### Listed for investigation", ""]
    lines += [f"- {item}" for item in listed] if listed else ["- None: no population group crosses a threshold."]
    return [*lines, ""]


def errors(result: dict[str, Any], names: dict[str, str]) -> list[str]:
    lines = [
        "## Error analysis",
        "",
        "The most confident misses on test (synthetic organizer data; no identifier; credit score rounded to "
        "tens, other values to one decimal).",
        "",
    ]
    for kind in LEARNED:
        for group, title in (
            ("high_estimate_negatives", "highest estimates among negatives"),
            ("low_estimate_positives", "lowest estimates among positives"),
        ):
            rows = [
                [e["estimate"], e["label"], *("missing" if v is None else v for v in e["features"].values())]
                for e in result["errors"][kind][group]
            ]
            lines += [f"### {names[kind]}, {title}", ""]
            lines += table(
                ["Estimate", "Label", "Credit score", "Tenure (months)", "Credit products", "Utilization"], rows
            )
            lines += [""]
    return lines
