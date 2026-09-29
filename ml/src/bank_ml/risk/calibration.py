"""Binary calibration on the dev calibration half, chosen on the dev selection half.

Candidates map a model's raw score (log-odds) to a probability: ``identity`` (the model's own sigmoid), ``platt``
(a logistic regression on the raw score), and ``isotonic`` (a non-decreasing step map, interpolated linearly and
clipped, exactly as the serving adapter evaluates it). The candidate with the lowest selection log loss wins; ties
go to the simpler map, in that order.
"""

from dataclasses import dataclass
from typing import Any

import numpy as np
from numpy.typing import NDArray
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

KINDS = ("identity", "platt", "isotonic")
EPS = 1e-12


def sigmoid(raw: NDArray[np.float64]) -> NDArray[np.float64]:
    return np.asarray(0.5 * (1.0 + np.tanh(0.5 * raw)), dtype=np.float64)


def log_loss(y: NDArray[np.int64], p: NDArray[np.float64]) -> float:
    clipped = np.clip(p, EPS, 1.0 - EPS)
    return float(-np.mean(y * np.log(clipped) + (1 - y) * np.log(1.0 - clipped)))


def fit(kind: str, raw: NDArray[np.float64], y: NDArray[np.int64]) -> dict[str, Any]:
    if kind == "identity":
        return {"kind": "identity"}
    if kind == "platt":
        model = LogisticRegression(C=1e6, max_iter=1000).fit(raw.reshape(-1, 1), y)
        return {"kind": "platt", "a": float(model.coef_[0][0]), "b": float(model.intercept_[0])}
    if kind == "isotonic":
        iso = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0).fit(raw, y)
        x, values = np.asarray(iso.X_thresholds_, dtype=np.float64), np.asarray(iso.y_thresholds_, dtype=np.float64)
        keep = np.concatenate([[True], np.diff(x) > 0])
        return {"kind": "isotonic", "x": [float(v) for v in x[keep]], "y": [float(v) for v in values[keep]]}
    raise ValueError(f"unknown calibrator {kind}")


def apply(calibrator: dict[str, Any], raw: NDArray[np.float64]) -> NDArray[np.float64]:
    kind = calibrator["kind"]
    if kind == "identity":
        return sigmoid(raw)
    if kind == "platt":
        return sigmoid(calibrator["a"] * raw + calibrator["b"])
    if kind == "isotonic":
        x = np.asarray(calibrator["x"], dtype=np.float64)
        values = np.asarray(calibrator["y"], dtype=np.float64)
        return np.asarray(np.interp(raw, x, values), dtype=np.float64)
    raise ValueError(f"unknown calibrator {kind}")


@dataclass(frozen=True)
class CalibrationChoice:
    calibrator: dict[str, Any]
    selection_log_loss: dict[str, float]


def choose(
    raw_calibration: NDArray[np.float64],
    y_calibration: NDArray[np.int64],
    raw_selection: NDArray[np.float64],
    y_selection: NDArray[np.int64],
) -> CalibrationChoice:
    fitted = {kind: fit(kind, raw_calibration, y_calibration) for kind in KINDS}
    losses = {kind: round(log_loss(y_selection, apply(fitted[kind], raw_selection)), 6) for kind in KINDS}
    best = min(KINDS, key=lambda kind: (losses[kind], KINDS.index(kind)))
    return CalibrationChoice(fitted[best], losses)
