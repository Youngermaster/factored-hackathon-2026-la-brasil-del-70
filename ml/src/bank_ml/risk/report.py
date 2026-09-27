"""Renders ``docs/evaluation/risk-estimator.md`` from the evaluation JSON (generated; do not edit by hand)."""

from typing import Any

from bank_ml.common.reports import pct, table
from bank_ml.risk.report_sections import calibration, disparities, errors, uncertainty

FRAMING = (
    "This is a risk estimate trained on synthetic organizer data. It is not a lending model, it is not validated for "
    "any real credit decision, and it never approves or declines anything. It is one input to the synthetic "
    "eligibility service (phase 06), which is also labeled synthetic."
)
ORDER = ("score_band@1", "score_band_reestimated", "logreg", "lgbm")
NAMES = {
    "score_band@1": "`score_band@1` (shipped priors)",
    "score_band_reestimated": "score bands re-estimated on train",
    "logreg": "`logreg`",
    "lgbm": "`lgbm`",
}


def ci(value: dict[str, float], digits: int = 3) -> str:
    return f"{value['estimate']:.{digits}f} [{value['low']:.{digits}f}, {value['high']:.{digits}f}]"


def _header(result: dict[str, Any]) -> list[str]:
    data = result["dataset"]
    learned = result["learned"]
    lines = ["# Evaluation: credit risk estimator (snapshot risk estimate)", "", FRAMING, ""]
    lines += [
        f"- Generated: {result['generated_at']} at commit `{result['git_sha']}` by `bank-ml risk evaluate`.",
        f"- Artifacts ({result['alias']}): `{learned['logreg']['artifact']}`, `{learned['lgbm']['artifact']}`.",
        f"- Dataset `{data['version']}`, hash `{data['hash'][:16]}`, snapshot {data['snapshot']}; rows: "
        + ", ".join(f"{split} {count:,}" for split, count in data["rows_per_split"].items())
        + ".",
        f"- Label `{result['label_definition']}`: any open credit product {result['dpd_threshold']} or more days past "
        "due at the single snapshot. **Cross-sectional**: it measures a concurrent association, not a forecast.",
        f"- Band cut points from `ELG-ALL-2`: {result['cuts'][0]:.2f} and {result['cuts'][1]:.2f}, margin "
        f"{result['cuts'][2]:.2f}.",
        "- Test was scored once, after every choice was made on train and dev. Intervals are 95% customer bootstraps.",
        "",
        "Filters: " + "; ".join(data["filters"]) + ".",
        "",
    ]
    return lines


def _headline(result: dict[str, Any]) -> list[str]:
    rows = []
    for name in ORDER:
        test = result["models"][name]["test"]
        rows.append(
            [
                NAMES[name],
                ci(test["roc_auc"]),
                ci(test["pr_auc"]),
                ci(test["brier"], 4),
                f"{test['log_loss']['estimate']:.4f}",
                ci(test["ece"], 4),
            ]
        )
    test = result["models"]["lgbm"]["test"]
    lines = [
        "## Headline (test split)",
        "",
        f"{test['customers']:,} test customers, {test['positives']:,} positive ({pct(test['prevalence'])}).",
        "",
    ]
    lines += table(["Model", "ROC AUC", "PR AUC", "Brier", "Log loss", "ECE"], rows)
    lines += ["", "### Paired differences (candidate minus reference, same resampled customers)", ""]
    diff_rows = []
    for kind, references in result["comparisons"].items():
        for reference, values in references.items():
            diff_rows.append(
                [
                    NAMES[kind],
                    NAMES[reference],
                    ci(values["roc_auc"], 4),
                    ci(values["pr_auc"], 4),
                    ci(values["brier"], 4),
                ]
            )
    lines += table(["Candidate", "Reference", "ROC AUC", "PR AUC", "Brier"], diff_rows)
    return [*lines, ""]


def _promotion(result: dict[str, Any]) -> list[str]:
    from bank_ml.risk.promotion import check

    lines = ["## Promotion rule check (pre-registered in `docs/plans/phase-10b.md`)", ""]
    for kind in ("logreg", "lgbm"):
        decision = check(result, kind)
        verdict = "meets the rule" if decision.promote else "does not meet the rule"
        lines += [f"- {NAMES[kind]} {verdict}: " + "; ".join(decision.reasons) + "."]
    lines += ["", "`make promote` records the decision (approver, time, commit, metrics compared) in the registry.", ""]
    return lines


def _bands(result: dict[str, Any]) -> list[str]:
    rows = []
    for name in ORDER:
        model = result["models"][name]["bands"]
        cells = [f"{pct(b['share'])} ({b['observed']:.3f})" if b["customers"] else "0" for b in model["bands"]]
        rows.append([NAMES[name], *cells, pct(model["borderline_share"])])
    lines = [
        "## Bands (test)",
        "",
        "Share of customers per band, with the observed positive rate in parentheses. "
        "Borderline: the interval, widened by the margin, reaches a cut point, so the synthetic eligibility "
        "service would ask for review.",
        "",
    ]
    return [*lines, *table(["Model", "Low", "Medium", "High", "Borderline"], rows), ""]


def render(result: dict[str, Any]) -> str:
    sections = [
        _header(result),
        _headline(result),
        _promotion(result),
        calibration(result, NAMES),
        _bands(result),
        uncertainty(result, NAMES, ci),
        disparities(result, NAMES, ci),
        errors(result, NAMES),
    ]
    return "\n".join(line for section in sections for line in section).rstrip() + "\n"
