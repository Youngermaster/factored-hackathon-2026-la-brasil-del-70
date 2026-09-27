"""Temperature scaling: one scalar that divides the logits, fitted on the dev split by minimizing the negative
log-likelihood. It changes confidences, never the ranking of classes, so accuracy is unchanged."""

import numpy as np
from numpy.typing import NDArray

TEMPERATURE_GRID = np.round(np.concatenate([np.arange(0.2, 1.0, 0.05), np.arange(1.0, 5.01, 0.1)]), 4)


def softmax(logits: NDArray[np.float64], temperature: float = 1.0) -> NDArray[np.float64]:
    scaled = logits / temperature
    scaled = scaled - scaled.max(axis=1, keepdims=True)
    exps = np.exp(scaled)
    return np.asarray(exps / exps.sum(axis=1, keepdims=True), dtype=np.float64)


def negative_log_likelihood(logits: NDArray[np.float64], labels: NDArray[np.int64], temperature: float) -> float:
    probabilities = softmax(logits, temperature)
    picked = probabilities[np.arange(len(labels)), labels]
    return float(-np.mean(np.log(np.clip(picked, 1e-12, 1.0))))


def fit_temperature(logits: NDArray[np.float64], labels: NDArray[np.int64]) -> float:
    """The grid temperature with the lowest dev NLL (ties to the value closest to 1)."""
    if len(labels) == 0:
        return 1.0
    scored = [
        (negative_log_likelihood(logits, labels, float(t)), abs(float(t) - 1.0), float(t)) for t in TEMPERATURE_GRID
    ]
    return min(scored)[2]
