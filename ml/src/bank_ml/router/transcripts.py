"""Why transcripts cannot label the router: the contact reason mapped through ``workflow_mapping.csv``, the
diversity of the customer text, and the agreement between the mapped reason and ``detected_intents``.

Reads the local warehouse (``gold.interactions_with_transcripts``, read only). The columns read are listed in
``SOURCE_COLUMNS`` and pass the leakage guard; no outcome column is read. Returns ``None`` when no warehouse exists.
"""

import csv
from collections import Counter
from pathlib import Path
from typing import Any

import duckdb

from bank_ml.common.leakage import assert_no_leakage
from bank_ml.common.reports import REPOSITORY_ROOT

MAPPING_FILE = REPOSITORY_ROOT / "data_platform" / "mappings" / "workflow_mapping.csv"
DEFAULT_WAREHOUSE = REPOSITORY_ROOT / "data" / "warehouse" / "warehouse.duckdb"
SOURCE_COLUMNS = ("contact_reason", "customer_text", "detected_intents")
_QUERY = """
    select contact_reason, customer_text, detected_intents
    from gold.interactions_with_transcripts
    where customer_text is not null and length(trim(customer_text)) > 0
"""


def contact_reason_mapping(path: Path = MAPPING_FILE) -> dict[str, str]:
    with path.open(encoding="utf-8") as stream:
        return {row["value"]: row["workflow_id"] for row in csv.DictReader(stream) if row["source"] == "contact_reason"}


def analyze(warehouse: Path = DEFAULT_WAREHOUSE) -> dict[str, Any] | None:
    if not warehouse.is_file():
        return None
    assert_no_leakage("router transcript analysis", SOURCE_COLUMNS)
    mapping = contact_reason_mapping()
    with duckdb.connect(str(warehouse), read_only=True) as connection:
        rows = connection.execute(_QUERY).fetchall()
    by_workflow = Counter(mapping.get(reason, "unmapped") for reason, _, _ in rows)
    intents = Counter(intent or "null" for _, _, intent in rows)
    intent_workflow = {intent: mapping.get(intent, "none") for intent in intents}
    agree = sum(1 for reason, _, intent in rows if intent and mapping.get(reason) == intent_workflow.get(intent))
    return {
        "texts": len(rows),
        "distinct_texts": len({text for _, text, _ in rows}),
        "by_mapped_workflow": dict(sorted(by_workflow.items())),
        "detected_intents": dict(sorted(intents.items())),
        "agreement": agree / len(rows) if rows else 0.0,
    }
