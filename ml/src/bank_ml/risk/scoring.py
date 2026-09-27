"""Vectorized scoring of a ``risk_classifier/1`` artifact with numpy, for evaluation over many rows.

It implements exactly the arithmetic of ``bank_agent.adapters.models.risk_artifact`` (the serving path), and
``assert_matches_adapter`` checks the two agree to 1e-9 on a sample every time a model is trained or evaluated, so
the reported metrics are the metrics of the served model.
"""

from typing import Any

import numpy as np
from numpy.typing import NDArray

from bank_agent.adapters.models.risk_artifact import RiskClassifierArtifact
from bank_agent.adapters.models.tree_ensemble import ZERO_THRESHOLD
from bank_ml.risk.calibration import apply

TOLERANCE = 1e-9


def linear_raw(scorer: dict[str, Any], x: NDArray[np.float64]) -> NDArray[np.float64]:
    absent = np.isnan(x)
    filled = np.where(absent, np.asarray(scorer["impute"]), x)
    standardized = (filled - np.asarray(scorer["mean"])) / np.asarray(scorer["scale"])
    total = standardized @ np.asarray(scorer["weights"]) + absent.astype(np.float64) @ np.asarray(
        scorer["missing_weights"]
    )
    return np.asarray(total + scorer["intercept"], dtype=np.float64)


def _tree(node: dict[str, Any], x: NDArray[np.float64], index: NDArray[np.int64], out: NDArray[np.float64]) -> None:
    if "value" in node:
        out[index] += node["value"]
        return
    values = x[index, node["feature"]]
    nan = np.isnan(values)
    safe = np.where(nan, 0.0, values)
    mode = node.get("missing", "none")
    if mode == "none":
        is_missing = np.zeros(len(values), dtype=bool)
    elif mode == "nan":
        is_missing = nan
    else:
        is_missing = nan | (np.abs(safe) <= ZERO_THRESHOLD)
    left = np.where(is_missing, bool(node.get("default_left", True)), safe <= node["threshold"])
    _tree(node["left"], x, index[left], out)
    _tree(node["right"], x, index[~left], out)


def trees_raw(scorer: dict[str, Any], x: NDArray[np.float64]) -> NDArray[np.float64]:
    out = np.zeros(len(x), dtype=np.float64)
    index = np.arange(len(x), dtype=np.int64)
    for tree in scorer["trees"]:
        _tree(tree, x, index, out)
    return out


def raw_scores(scorer: dict[str, Any], x: NDArray[np.float64]) -> NDArray[np.float64]:
    return linear_raw(scorer, x) if scorer["kind"] == "linear" else trees_raw(scorer, x)


def probabilities(member: dict[str, Any], x: NDArray[np.float64]) -> NDArray[np.float64]:
    return apply(member["calibrator"], raw_scores(member["scorer"], x))


def bounds(
    interval: dict[str, Any], x: NDArray[np.float64], raw: NDArray[np.float64]
) -> tuple[NDArray[Any], NDArray[Any]]:
    if interval["method"] == "bootstrap":
        members = np.vstack([probabilities(member, x) for member in interval["members"]])
        return np.quantile(members, interval["lower"], axis=0), np.quantile(members, interval["upper"], axis=0)
    position = np.searchsorted(np.asarray(interval["edges"], dtype=np.float64), raw, side="right")
    return np.asarray(interval["p0"])[position], np.asarray(interval["p1"])[position]


def estimate(artifact: dict[str, Any], x: NDArray[np.float64]) -> tuple[NDArray[Any], NDArray[Any], NDArray[Any]]:
    """``(probability, low, high)`` per row, the interval widened to contain the probability."""
    raw = raw_scores(artifact["scorer"], x)
    probability = apply(artifact["calibrator"], raw)
    low, high = bounds(artifact["interval"], x, raw)
    return probability, np.minimum(low, probability), np.maximum(high, probability)


def assert_matches_adapter(artifact: dict[str, Any], x: NDArray[np.float64]) -> float:
    """The largest absolute difference between numpy and the serving artifact; raises above the tolerance."""
    served = RiskClassifierArtifact.model_validate(artifact)
    numpy_values = np.column_stack(estimate(artifact, x))
    adapter_values = np.array([served.estimate(list(row)) for row in x], dtype=np.float64).reshape(-1, 3)
    difference = float(np.max(np.abs(numpy_values - adapter_values))) if len(x) else 0.0
    if difference > TOLERANCE:
        raise ValueError(f"numpy scoring differs from the serving adapter by {difference:.2e}")
    return difference
