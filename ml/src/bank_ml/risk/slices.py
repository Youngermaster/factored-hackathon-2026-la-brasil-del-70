"""Bands, slices, and the disparity report.

Bands use the policy's cut points (``ELG-ALL-2``, read from the pack): low below the medium cut, medium below the high
cut, high from there. An interval is borderline, as the synthetic eligibility service reads it, when widened by the
margin it reaches a cut: ``low < cut + margin`` and ``high > cut - margin`` for either cut.

Slices: country, segment, within-country income tertile, and (diagnostic only) credit product count. Segment and
country are evaluation slices only. A cell with fewer than ``SMALL_CUSTOMERS`` customers or ``SMALL_POSITIVES``
positives is flagged small. A group is listed for investigation when, against the rest of the population, its
calibration gap (mean estimate minus observed rate) differs by more than ``GAP_THRESHOLD`` with a bootstrap interval
excluding zero, its ROC AUC differs by more than ``AUC_THRESHOLD``, or its low-band share ratio is below
``LOW_BAND_RATIO``. This is a disparity report for investigation, not a fairness certification.
"""

from collections.abc import Sequence
from typing import Any

import numpy as np
from numpy.typing import NDArray

from bank_agent.adapters.policy.filesystem import FilesystemPolicyRepository
from bank_agent.bootstrap.settings import DEFAULT_POLICY_DIR
from bank_ml.common.seeds import seed_for
from bank_ml.risk.metrics import bootstrap, on_rows, roc_auc

CUT_CLAUSE = "ELG-ALL-2"
SMALL_CUSTOMERS, SMALL_POSITIVES = 300, 30
GAP_THRESHOLD, AUC_THRESHOLD, LOW_BAND_RATIO = 0.02, 0.05, 0.8
SLICE_SAMPLES = 400
DISPARITY_DIMENSIONS = ("country", "segment", "income_band")
DIMENSIONS = (*DISPARITY_DIMENSIONS, "credit_products")
"""``credit_products`` is diagnostic (the model's main feature, not a population group): reported, never listed."""


def policy_cuts(policy_dir: Any = DEFAULT_POLICY_DIR) -> tuple[float, float, float]:
    """``(medium cut, high cut, margin)`` from the pack, so the bands never drift from the eligibility service."""
    params = FilesystemPolicyRepository.from_directory(policy_dir).pack.params(CUT_CLAUSE)
    return (
        int(str(params["risk_cut_medium_bps"])) / 10_000,
        int(str(params["risk_cut_high_bps"])) / 10_000,
        int(str(params["borderline_margin_bps"])) / 10_000,
    )


def bands(p: NDArray[np.float64], cut_medium: float, cut_high: float) -> NDArray[np.str_]:
    return np.where(p < cut_medium, "low", np.where(p < cut_high, "medium", "high"))


def borderline(low: NDArray[Any], high: NDArray[Any], cuts: Sequence[float], margin: float) -> NDArray[np.bool_]:
    hits = np.zeros(len(low), dtype=bool)
    for cut in cuts:
        hits |= (low < cut + margin) & (high > cut - margin)
    return hits


def band_table(
    y: NDArray[Any], p: NDArray[Any], low: NDArray[Any], high: NDArray[Any], cuts: tuple[float, float, float]
) -> dict[str, Any]:
    labels = bands(p, cuts[0], cuts[1])
    table = []
    for band in ("low", "medium", "high"):
        mask = labels == band
        table.append(
            {
                "band": band,
                "customers": int(mask.sum()),
                "share": float(mask.mean()) if len(p) else 0.0,
                "observed": float(y[mask].mean()) if mask.any() else float("nan"),
            }
        )
    edge = borderline(low, high, cuts[:2], cuts[2])
    return {"bands": table, "borderline_share": float(edge.mean()) if len(p) else 0.0}


def product_bucket(count: int) -> str:
    return str(count) if count < 4 else "4+"


def group_keys(rows: Sequence[Any], dimension: str) -> NDArray[np.str_]:
    if dimension == "credit_products":
        return np.array([product_bucket(row.credit_product_count) for row in rows])
    return np.array([str(getattr(row, dimension)) for row in rows])


def _gap(y: NDArray[Any], p: NDArray[Any]) -> float:
    return float(p.mean() - y.mean()) if len(y) else float("nan")


def slice_report(
    rows: Sequence[Any],
    y: NDArray[Any],
    p: NDArray[Any],
    low: NDArray[Any],
    high: NDArray[Any],
    cuts: tuple[float, float, float],
    name: str,
) -> dict[str, list[dict[str, Any]]]:
    low_band = bands(p, cuts[0], cuts[1]) == "low"
    edge = borderline(low, high, cuts[:2], cuts[2])
    report: dict[str, list[dict[str, Any]]] = {}
    for dimension in DIMENSIONS:
        keys = group_keys(rows, dimension)
        entries = []
        for group in sorted(set(keys.tolist())):
            inside, outside = keys == group, keys != group
            yi, pi, yo, po = y[inside], p[inside], y[outside], p[outside]
            n, positives = int(inside.sum()), int(yi.sum())
            tag = f"{name}:{dimension}:{group}"
            gap = bootstrap(n, on_rows(_gap, yi, pi), f"{tag}:gap", SLICE_SAMPLES)
            gap_diff = _gap_difference(yi, pi, yo, po, f"{tag}:gapdiff")
            auc = bootstrap(n, on_rows(roc_auc, yi, pi), f"{tag}:auc", SLICE_SAMPLES)
            rest_auc = roc_auc(yo, po)
            low_share = float(low_band[inside].mean())
            rest_low = float(low_band[outside].mean()) if outside.any() else 0.0
            ratio = low_share / rest_low if rest_low > 0 else float("nan")
            small = n < SMALL_CUSTOMERS or positives < SMALL_POSITIVES
            reasons = []
            if abs(gap_diff["estimate"]) > GAP_THRESHOLD and (gap_diff["low"] > 0 or gap_diff["high"] < 0):
                reasons.append("calibration gap")
            if not np.isnan(auc["estimate"]) and abs(auc["estimate"] - rest_auc) > AUC_THRESHOLD:
                reasons.append("roc auc")
            if not np.isnan(ratio) and ratio < LOW_BAND_RATIO:
                reasons.append("low-band share ratio")
            entries.append(
                {
                    "group": group,
                    "customers": n,
                    "positives": positives,
                    "prevalence": float(yi.mean()) if n else float("nan"),
                    "mean_estimate": float(pi.mean()) if n else float("nan"),
                    "gap": gap,
                    "gap_vs_rest": gap_diff,
                    "roc_auc": auc,
                    "roc_auc_rest": rest_auc,
                    "low_band_share": low_share,
                    "low_band_ratio": ratio,
                    "borderline_share": float(edge[inside].mean()) if n else 0.0,
                    "small_cell": small,
                    "listed": bool(reasons) and not small and dimension in DISPARITY_DIMENSIONS,
                    "reasons": reasons,
                }
            )
        report[dimension] = entries
    return report


def _gap_difference(
    yi: NDArray[Any], pi: NDArray[Any], yo: NDArray[Any], po: NDArray[Any], name: str
) -> dict[str, float]:
    """Group gap minus rest gap, resampling the group and the rest independently (they are disjoint customers)."""
    estimate = _gap(yi, pi) - _gap(yo, po)
    if len(yi) < 2 or len(yo) < 2:
        return {"estimate": estimate, "low": float("nan"), "high": float("nan")}
    generator = np.random.default_rng(seed_for("bootstrap", name))
    values = []
    for _ in range(SLICE_SAMPLES):
        a = generator.integers(0, len(yi), size=len(yi))
        b = generator.integers(0, len(yo), size=len(yo))
        values.append(_gap(yi[a], pi[a]) - _gap(yo[b], po[b]))
    return {"estimate": estimate, "low": float(np.quantile(values, 0.025)), "high": float(np.quantile(values, 0.975))}
