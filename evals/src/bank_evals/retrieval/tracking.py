"""Experiment tracking for evaluations: MLflow with a local file store by default, or nothing.

MLflow 3.16 keeps the file store in maintenance mode and refuses it unless ``MLFLOW_ALLOW_FILE_STORE=true``; the
team asked for the file store (``file:./mlruns``, gitignored), so the tracker sets that flag for ``file:`` URIs
only. MLflow is imported when a run is logged, so importing this module stays cheap.
"""

import os
from collections.abc import Mapping
from typing import Protocol

ParamValue = str | int | float


class ExperimentTracker(Protocol):
    def log_run(
        self,
        run_name: str,
        params: Mapping[str, ParamValue],
        metrics: Mapping[str, float],
        tags: Mapping[str, str],
        artifacts: Mapping[str, str],
    ) -> str | None:
        """Record one run; return its id, or ``None`` when nothing is recorded."""
        ...


class NullTracker:
    def log_run(
        self,
        run_name: str,
        params: Mapping[str, ParamValue],
        metrics: Mapping[str, float],
        tags: Mapping[str, str],
        artifacts: Mapping[str, str],
    ) -> str | None:
        return None


class MlflowTracker:
    """Logs parameters, metrics, tags, and text artifacts (for example the Markdown report) to one experiment."""

    def __init__(self, tracking_uri: str, experiment: str = "retrieval") -> None:
        self._uri = tracking_uri
        self._experiment = experiment

    def log_run(
        self,
        run_name: str,
        params: Mapping[str, ParamValue],
        metrics: Mapping[str, float],
        tags: Mapping[str, str],
        artifacts: Mapping[str, str],
    ) -> str | None:
        if self._uri.startswith("file:"):
            os.environ.setdefault("MLFLOW_ALLOW_FILE_STORE", "true")
        os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
        import mlflow  # imported on first use

        mlflow.set_tracking_uri(self._uri)
        mlflow.set_experiment(self._experiment)
        with mlflow.start_run(run_name=run_name) as run:
            mlflow.log_params(dict(params))
            mlflow.log_metrics(dict(metrics))
            mlflow.set_tags(dict(tags))
            for name, text in artifacts.items():
                mlflow.log_text(text, name)
            return str(run.info.run_id)
