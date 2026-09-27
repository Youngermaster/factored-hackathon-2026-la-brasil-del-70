"""The automatable-share labeling task (``docs/analysis/labeling-protocol.md``).

- ``select_sample`` draws a stratified sample of transcripts per workflow (equal allocation across
  countries, ranked by a seeded hash), with synthetic ids and customer text only.
- ``write_sample`` writes it for the labelers and never overwrites a file that already holds human labels.
- ``prelabel`` is a deterministic keyword rule. Its output goes to a separate file with
  ``review_status=pending``; it is never read back as a label.
- ``read_labels`` summarizes the human labels per workflow, or reports that they are pending.
"""

import csv
import hashlib
import io
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from bank_data.analysis.config import WORKFLOWS
from bank_data.analysis.stats import cohen_kappa

LABEL_VALUES = ("yes", "no", "unclear")
LABEL_COLUMNS: tuple[str, ...] = (
    "labeler_1_resolvable",
    "labeler_1_matches_workflow",
    "labeler_2_resolvable",
    "labeler_2_matches_workflow",
    "adjudicated_resolvable",
    "adjudicated_matches_workflow",
    "notes",
)
SAMPLE_COLUMNS: tuple[str, ...] = ("item_id", "interaction_id", "workflow_stratum", "customer_text", *LABEL_COLUMNS)
PRELABEL_COLUMNS: tuple[str, ...] = (
    "item_id",
    "workflow_stratum",
    "prelabel_topic",
    "prelabel_resolvable",
    "prelabel_matches_workflow",
    "prelabel_rule",
    "review_status",
)
PENDING = "pending human labels"


def sample_rank(seed: str, item: str) -> str:
    return hashlib.sha256(f"{seed}:{item}".encode()).hexdigest()


def _allocate(total: int, available: dict[str, int]) -> dict[str, int]:
    """Equal allocation across strata; a stratum short of rows passes its shortfall to the others."""
    allocation = dict.fromkeys(available, 0)
    remaining = total
    open_strata = sorted(available)
    while remaining > 0 and open_strata:
        share, extra = divmod(remaining, len(open_strata))
        progressed = False
        for index, stratum in enumerate(open_strata):
            want = share + (1 if index < extra else 0)
            take = min(want, available[stratum] - allocation[stratum])
            allocation[stratum] += take
            remaining -= take
            progressed = progressed or take > 0
        open_strata = [stratum for stratum in open_strata if allocation[stratum] < available[stratum]]
        if not progressed:
            break
    return allocation


def select_sample(candidates: pd.DataFrame, *, per_workflow: int, seed: str) -> pd.DataFrame:
    """Up to ``per_workflow`` items per in-scope workflow, equally allocated across countries.

    ``candidates`` has ``interaction_id``, ``workflow``, ``country``, ``customer_text``. The result has the
    sample columns, label columns empty, ordered by workflow and hash rank; ``item_id`` is ``LBL-0001``...
    """
    chosen: list[pd.DataFrame] = []
    for workflow in WORKFLOWS:
        rows = candidates[candidates["workflow"] == workflow].copy()
        if rows.empty:
            continue
        rows["country"] = rows["country"].fillna("unknown")
        rows["rank"] = [sample_rank(seed, str(item)) for item in rows["interaction_id"]]
        rows = rows.sort_values(["rank", "interaction_id"])
        counts = rows.groupby("country").size().to_dict()
        allocation = _allocate(per_workflow, {str(key): int(value) for key, value in counts.items()})
        picked = pd.concat(
            [rows[rows["country"] == country].head(size) for country, size in sorted(allocation.items()) if size]
        )
        chosen.append(picked.sort_values(["rank", "interaction_id"]))
    columns = list(SAMPLE_COLUMNS)
    if not chosen:
        return pd.DataFrame(columns=columns)
    sample = pd.concat(chosen, ignore_index=True)
    frame = pd.DataFrame(
        {
            "item_id": [f"LBL-{index + 1:04d}" for index in range(len(sample))],
            "interaction_id": sample["interaction_id"].astype(str),
            "workflow_stratum": sample["workflow"].astype(str),
            "customer_text": sample["customer_text"].astype(str).str.strip(),
        }
    )
    for column in LABEL_COLUMNS:
        frame[column] = ""
    return frame[columns]


@dataclass(frozen=True)
class Prelabel:
    topic: str
    resolvable: str
    matches_workflow: str
    rule: str


_TOPIC_WORKFLOW = {
    "balance_inquiry": "account_inquiry",
    "card_block": "card_support",
    "dispute_new": "dispute",
    "credit_product_info": "credit",
}
_RULES: tuple[tuple[str, tuple[str, ...], str], ...] = (
    ("balance_keywords", ("saldo",), "balance_inquiry"),
    ("card_loss_keywords", ("bloquear", "bloqueo", "robada", "robaron", "perdí mi tarjeta", "extravi"), "card_block"),
    ("dispute_keywords", ("no reconozco", "cargo no", "disputa", "cobro indebido", "fraude"), "dispute_new"),
    ("credit_keywords", ("préstamo", "prestamo", "crédito hipotecario", "solicitar un crédito"), "credit_product_info"),
)


def prelabel(text: str, stratum: str) -> Prelabel:
    """A deterministic keyword rule: the first rule whose keyword appears decides the topic. A balance
    question is answerable from records (``yes``); other topics need a human reading (``unclear``)."""
    lowered = text.lower()
    for rule, keywords, topic in _RULES:
        if any(keyword in lowered for keyword in keywords):
            resolvable = "yes" if topic == "balance_inquiry" else "unclear"
            matches = "yes" if _TOPIC_WORKFLOW[topic] == stratum else "no"
            return Prelabel(topic, resolvable, matches, rule)
    return Prelabel("unknown", "unclear", "unclear", "no_rule")


def prelabel_frame(sample: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for item_id, stratum, text in zip(
        sample["item_id"], sample["workflow_stratum"], sample["customer_text"], strict=True
    ):
        label = prelabel(str(text), str(stratum))
        rows.append(
            {
                "item_id": item_id,
                "workflow_stratum": stratum,
                "prelabel_topic": label.topic,
                "prelabel_resolvable": label.resolvable,
                "prelabel_matches_workflow": label.matches_workflow,
                "prelabel_rule": label.rule,
                "review_status": "pending",
            }
        )
    return pd.DataFrame(rows, columns=list(PRELABEL_COLUMNS))


def _csv_text(frame: pd.DataFrame) -> str:
    buffer = io.StringIO()
    frame.to_csv(buffer, index=False, lineterminator="\n", quoting=csv.QUOTE_MINIMAL)
    return buffer.getvalue()


def has_human_labels(path: Path) -> bool:
    if not path.exists():
        return False
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    present = [column for column in LABEL_COLUMNS if column in frame.columns]
    return any(frame[column].str.strip().ne("").any() for column in present)


def write_sample(path: Path, sample: pd.DataFrame) -> str:
    """Write the labeling file; ``kept`` when an existing file already holds human labels (never
    overwritten), else ``written``."""
    if has_human_labels(path):
        return "kept"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_csv_text(sample), encoding="utf-8")
    return "written"


def write_prelabels(path: Path, prelabels: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_csv_text(prelabels), encoding="utf-8")


@dataclass
class WorkflowLabels:
    workflow: str
    items: int = 0
    adjudicated: int = 0
    matching: int = 0
    yes: int = 0
    no: int = 0
    unclear: int = 0
    invalid: int = 0
    double_labeled: int = 0
    kappa_resolvable: float | None = None
    status: str = PENDING
    share: float | None = None

    @property
    def usable(self) -> bool:
        return self.share is not None


@dataclass
class LabelSummary:
    file_present: bool
    workflows: dict[str, WorkflowLabels] = field(default_factory=dict)

    def share_for(self, workflow: str) -> float | None:
        labels = self.workflows.get(workflow)
        return labels.share if labels is not None else None


def _clean(value: object) -> str:
    return str(value).strip().lower() if value is not None else ""


def read_labels(path: Path, *, min_matching: int) -> LabelSummary:
    """Per workflow: adjudicated items, items whose text matches the workflow, and the automatable share
    over matching items (``unclear`` counts as not automatable). The share is set only with at least
    ``min_matching`` matching items; otherwise the status explains why."""
    summary = LabelSummary(file_present=path.exists())
    for workflow in WORKFLOWS:
        summary.workflows[workflow] = WorkflowLabels(workflow)
    if not path.exists():
        return summary
    frame = pd.read_csv(path, dtype=str, keep_default_na=False)
    missing = [column for column in SAMPLE_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"labeling file lacks columns: {missing}")
    for workflow in WORKFLOWS:
        rows = frame[frame["workflow_stratum"] == workflow]
        labels = summary.workflows[workflow]
        labels.items = len(rows)
        first, second = [], []
        for _, row in rows.iterrows():
            one, two = _clean(row["labeler_1_resolvable"]), _clean(row["labeler_2_resolvable"])
            if one in LABEL_VALUES and two in LABEL_VALUES:
                first.append(one)
                second.append(two)
            resolvable = _clean(row["adjudicated_resolvable"])
            matches = _clean(row["adjudicated_matches_workflow"])
            if not resolvable and not matches:
                continue
            if resolvable not in LABEL_VALUES or matches not in LABEL_VALUES:
                labels.invalid += 1
                continue
            labels.adjudicated += 1
            if matches != "yes":
                continue
            labels.matching += 1
            if resolvable == "yes":
                labels.yes += 1
            elif resolvable == "no":
                labels.no += 1
            else:
                labels.unclear += 1
        labels.double_labeled = len(first)
        labels.kappa_resolvable = cohen_kappa(first, second)
        if labels.adjudicated == 0:
            labels.status = PENDING
        elif labels.matching < min_matching:
            labels.status = f"insufficient matching labels ({labels.matching} of {min_matching})"
        else:
            labels.status = "labeled"
            labels.share = labels.yes / labels.matching
    return summary
