"""The reason-to-workflow mapping covers every observed reason and uses only valid workflow and intent values.

Observed values come from the committed organizer sample and the team-made fixture (the full delivery is not
available in CI); `bank-data analysis` repeats the check on the full data and reports any unmapped value as a
stop condition.
"""

import csv
from pathlib import Path

from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_data.analysis.config import OTHER, WORKFLOWS, load_mapping, load_scoring
from bank_data.contracts.canonical import canonical_value
from bank_data.contracts.tables import REASON_CATEGORIES
from bank_data.settings import DATA_PLATFORM_ROOT, DEFAULT_SAMPLE_DIR

MAPPING = load_mapping()
SOURCES = (DEFAULT_SAMPLE_DIR, *sorted((DATA_PLATFORM_ROOT / "fixtures" / "late_arrival").glob("*/")))


def _rows(table: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for root in SOURCES:
        for path in sorted(Path(root).glob(f"{table}/**/*.csv")):
            with path.open(encoding="utf-8-sig", newline="") as handle:
                rows.extend(csv.DictReader(handle))
    return rows


def test_every_observed_contact_reason_is_mapped() -> None:
    reasons = {row["contact_reason"].strip() for row in _rows("call_center_interactions")}
    assert reasons, "the sample and the fixture must contain interactions"
    unmapped = sorted(reason for reason in reasons if MAPPING.lookup("contact_reason", reason) is None)
    assert unmapped == []


def test_every_observed_complaint_category_and_subcategory_is_mapped() -> None:
    pairs = {(row["category"].strip(), row["subcategory"].strip()) for row in _rows("complaints")}
    assert pairs, "the sample and the fixture must contain complaints"
    unmapped = sorted(pair for pair in pairs if MAPPING.lookup("complaint_category", *pair) is None)
    assert unmapped == []


def test_every_accepted_reason_category_is_mapped_consistently_with_its_contact_reason() -> None:
    for value in REASON_CATEGORIES:
        code = canonical_value("reason_category", value)
        category_row = MAPPING.lookup("reason_category", code)
        reason_row = MAPPING.lookup("contact_reason", value)
        assert category_row is not None, code
        assert reason_row is not None, value
        for scenario in ("primary", "strict", "alternative"):
            assert category_row.workflow_for(scenario) == reason_row.workflow_for(scenario)


def test_source_spellings_of_a_reason_map_like_their_canonical_code() -> None:
    for row in MAPPING.for_source("contact_reason"):
        code = canonical_value("reason_category", row.value)
        category_row = MAPPING.lookup("reason_category", code)
        assert category_row is not None, row.value
        assert category_row.workflow_id == row.workflow_id


def test_workflow_ids_are_workflow_id_values_or_other() -> None:
    allowed = {workflow.value for workflow in WorkflowId} | {OTHER}
    assert set(WORKFLOWS) == {workflow.value for workflow in WorkflowId}
    for row in MAPPING.rows:
        assert {row.workflow_id, row.strict_workflow_id, row.alternative_workflow_id} <= allowed


def test_sub_intents_are_intents_owned_by_the_mapped_workflow() -> None:
    for row in MAPPING.rows:
        if not row.sub_intent:
            continue
        owner = WORKFLOW_CATALOG.workflow_for(Intent(row.sub_intent))
        assert owner is not None, row
        assert owner.value == row.workflow_id, row


def test_scored_sub_intents_are_exactly_the_intents_each_workflow_owns() -> None:
    scoring = load_scoring()
    for name, spec in scoring.sub_intents.items():
        owner = WORKFLOW_CATALOG.workflow_for(Intent(name))
        assert owner is not None, name
        assert owner.value == spec.workflow, name
    for workflow in WorkflowId:
        owned = set(WORKFLOW_CATALOG.descriptor(workflow).intents)
        scored = {Intent(name) for name, spec in scoring.sub_intents.items() if spec.workflow == workflow.value}
        assert scored == owned, workflow
