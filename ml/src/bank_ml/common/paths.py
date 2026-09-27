"""Where ``bank-ml`` reads and writes. Everything under ``data/`` is gitignored; reports go to ``docs/``."""

from bank_agent.bootstrap.settings import DEFAULT_MODEL_REGISTRY_DIR
from bank_ml.common.reports import REPOSITORY_ROOT

DATA_DIR = REPOSITORY_ROOT / "data"
ARTIFACTS_DIR = DATA_DIR / "artifacts" / "ml"
DATASETS_DIR = ARTIFACTS_DIR / "datasets"
EVALUATIONS_DIR = ARTIFACTS_DIR / "evaluations"
RUNS_DIR = ARTIFACTS_DIR / "runs"
REGISTRY_DIR = DEFAULT_MODEL_REGISTRY_DIR
GOLD_DIR = DATA_DIR / "warehouse" / "gold"
LABELING_DIR = DATA_DIR / "labeling"
DOCS_EVALUATION_DIR = REPOSITORY_ROOT / "docs" / "evaluation"
