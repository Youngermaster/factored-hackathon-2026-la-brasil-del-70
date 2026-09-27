"""Experiment tracking: every training run logs parameters, metrics, dataset hashes, the git commit, the
environment, and artifacts to MLflow. The default store is SQLite (``sqlite:///mlruns.db``, gitignored), because
MLflow keeps the file store in maintenance mode; ``BANK_ML_TRACKING_URI=none`` disables tracking."""

import os
import platform
from collections.abc import Mapping
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Protocol

DEFAULT_TRACKING_URI = "sqlite:///mlruns.db"
PARAM_LIMIT = 500
_PACKAGES = ("bank-ml", "bank-agent", "numpy", "scikit-learn", "lightgbm", "datasketch", "rapidfuzz", "mlflow-skinny")

ParamValue = str | int | float | bool


def environment_tags() -> dict[str, str]:
    tags = {"python": platform.python_version(), "platform": platform.platform(terse=True)}
    for package in _PACKAGES:
        try:
            tags[f"version.{package}"] = version(package)
        except PackageNotFoundError:
            tags[f"version.{package}"] = "absent"
    return tags


class Tracker(Protocol):
    def log_run(
        self,
        experiment: str,
        run_name: str,
        params: Mapping[str, ParamValue],
        metrics: Mapping[str, float],
        tags: Mapping[str, str],
        artifacts: Mapping[str, Path],
    ) -> str | None:
        """Record one run; return its id, or ``None`` when nothing is recorded."""
        ...


class NullTracker:
    def log_run(
        self,
        experiment: str,
        run_name: str,
        params: Mapping[str, ParamValue],
        metrics: Mapping[str, float],
        tags: Mapping[str, str],
        artifacts: Mapping[str, Path],
    ) -> str | None:
        return None


class MlflowTracker:
    def __init__(self, uri: str = DEFAULT_TRACKING_URI) -> None:
        self._uri = uri

    def log_run(
        self,
        experiment: str,
        run_name: str,
        params: Mapping[str, ParamValue],
        metrics: Mapping[str, float],
        tags: Mapping[str, str],
        artifacts: Mapping[str, Path],
    ) -> str | None:
        if self._uri.startswith("file:"):
            os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
        os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
        import mlflow  # imported on first use; heavy

        mlflow.set_tracking_uri(self._uri)
        mlflow.set_experiment(experiment)
        with mlflow.start_run(run_name=run_name) as run:
            mlflow.log_params({key: str(value)[:PARAM_LIMIT] for key, value in params.items()})
            mlflow.log_metrics(dict(metrics))
            mlflow.set_tags({**environment_tags(), **tags})
            for folder, path in artifacts.items():
                mlflow.log_artifact(str(path), artifact_path=folder)
            return str(run.info.run_id)


def tracker_for(uri: str | None) -> Tracker:
    chosen = uri or os.environ.get("BANK_ML_TRACKING_URI") or DEFAULT_TRACKING_URI
    return NullTracker() if chosen == "none" else MlflowTracker(chosen)
