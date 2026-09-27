"""``bank-data analysis``: read the built warehouse, compute the evidence and scores, and write every report,
figure, and labeling file.

Reports go to ``docs/analysis/`` only for the organizer data (source ``s3``); other sources write next to their
warehouse, so a sample or fixture run never overwrites the committed reports. The labeling files go to
``data/labeling/`` (gitignored) for ``s3``.
"""

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import duckdb

from bank_data.analysis import evidence, figures, labeling, queries, render
from bank_data.analysis.config import (
    DEFAULT_COST_FILE,
    DEFAULT_MAPPING_FILE,
    DEFAULT_SCORING_FILE,
    WORKFLOWS,
    load_costs,
    load_mapping,
    load_scoring,
)
from bank_data.errors import ConfigurationError
from bank_data.settings import REPOSITORY_ROOT

EVIDENCE_FILE = "workflow-evidence.md"
SCORES_FILE = "workflow-scores.md"
RESULTS_FILE = "analysis-results.json"
SAMPLE_FILE = "automatable_sample.csv"
PRELABEL_FILE = "automatable_prelabels.csv"
EXPECTED_OUTPUTS: tuple[str, ...] = (
    EVIDENCE_FILE,
    SCORES_FILE,
    RESULTS_FILE,
    *(f"figures/{name}" for name in figures.FIGURE_NAMES),
)
SOURCE_DESCRIPTIONS = {
    "s3": "full organizer delivery",
    "sample": "committed 74-customer sample, not statistically representative",
    "local": "local directory (test fixture)",
}


@dataclass(frozen=True)
class AnalysisRun:
    warehouse_db: Path
    output_dir: Path
    labeling_dir: Path
    source: str
    dataset_version: str
    generated_at: datetime
    git_sha: str
    mapping_file: Path = DEFAULT_MAPPING_FILE
    scoring_file: Path = DEFAULT_SCORING_FILE
    cost_file: Path = DEFAULT_COST_FILE


@dataclass(frozen=True)
class AnalysisOutcome:
    written: list[Path]
    blocked: list[str]
    labeling_status: str
    ranking: list[str]
    scores: dict[str, float]


def shown(path: Path) -> str:
    try:
        return path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def run_analysis(run: AnalysisRun) -> AnalysisOutcome:
    if not run.warehouse_db.exists():
        raise ConfigurationError("no built warehouse; run `bank-data build` first")
    scoring = load_scoring(run.scoring_file)
    sample_path = run.labeling_dir / SAMPLE_FILE
    prelabel_path = run.labeling_dir / PRELABEL_FILE
    try:
        labels = labeling.read_labels(sample_path, min_matching=scoring.labels.min_matching_labels_per_workflow)
    except ValueError as error:
        raise ConfigurationError(f"unreadable labeling file {sample_path.name}: {error}") from None
    inputs = evidence.AnalysisInputs(load_mapping(run.mapping_file), scoring, load_costs(run.cost_file), labels)
    connection = duckdb.connect(str(run.warehouse_db), read_only=True)
    try:
        results = evidence.compute(connection, inputs)
        candidates = queries.labeling_candidates(connection)
    finally:
        connection.close()

    sample = labeling.select_sample(
        candidates, per_workflow=scoring.labels.target_per_workflow, seed=scoring.labels.seed
    )
    status = labeling.write_sample(sample_path, sample)
    prelabels = labeling.prelabel_frame(sample)
    labeling.write_prelabels(prelabel_path, prelabels)
    summary = (
        prelabels.groupby(["workflow_stratum", "prelabel_topic", "prelabel_matches_workflow"]).size().reset_index()
        if len(prelabels)
        else None
    )
    results["labeling_export"] = {
        "path": shown(sample_path),
        "prelabel_path": shown(prelabel_path),
        "status": "written" if status == "written" else "kept: the existing file holds human labels",
        "items": len(sample),
        "per_workflow": {workflow: int((sample["workflow_stratum"] == workflow).sum()) for workflow in WORKFLOWS},
        "prelabel_summary": [
            [str(stratum), str(topic), str(matches), int(count)]
            for stratum, topic, matches, count in (summary.itertuples(index=False) if summary is not None else [])
        ],
    }

    meta: dict[str, Any] = {
        "generated_at": run.generated_at.isoformat(),
        "git_sha": run.git_sha,
        "source": run.source,
        "source_description": SOURCE_DESCRIPTIONS.get(run.source, run.source),
        "dataset_version": run.dataset_version,
        "first_day": results["dataset"]["first_day"],
        "last_day": results["dataset"]["last_day"],
        "preregistration_version": scoring.version,
        "bootstrap_resamples": scoring.statistics.bootstrap_resamples,
    }
    run.output_dir.mkdir(parents=True, exist_ok=True)
    written = [
        _write(run.output_dir / EVIDENCE_FILE, render.render_evidence(results, meta)),
        _write(run.output_dir / SCORES_FILE, render.render_scores(results, meta)),
        _write(
            run.output_dir / RESULTS_FILE,
            json.dumps({"meta": meta, "results": results}, indent=1, sort_keys=True, default=str) + "\n",
        ),
    ]
    written += figures.write_figures(results, run.output_dir / "figures")
    primary = results["scores"]["scenarios"]["primary"]
    return AnalysisOutcome(
        written=written,
        blocked=list(results["stop_conditions"]["blocked"]),
        labeling_status=status,
        ranking=list(primary["ranking"]),
        scores=dict(primary["scores"]),
    )


def _write(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path
