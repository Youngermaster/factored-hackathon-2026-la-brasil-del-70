import pandas as pd

from bank_data.contracts.evolution import ChangeKind, compare_columns, detect_type_changes, normalize_name, schema_hash
from bank_data.contracts.tables import table_spec
from bank_data.contracts.validation import parse_frame

RATES = table_spec("daily_exchange_rates")
COLUMNS = list(RATES.column_names)


def test_identical_header_is_unchanged() -> None:
    change = compare_columns(COLUMNS, RATES)
    assert change.kind is ChangeKind.UNCHANGED
    assert change.reason_code is None
    assert change.describe() == "no change"


def test_extra_column_is_additive() -> None:
    change = compare_columns([*COLUMNS, "Provider_Note "], RATES)
    assert change.kind is ChangeKind.ADDITIVE
    assert change.added == ("provider_note",)
    assert change.reason_code == "schema_additive_column"


def test_missing_column_is_breaking_even_with_additions() -> None:
    change = compare_columns([name for name in COLUMNS if name != "buy_rate"] + ["new_rate"], RATES)
    assert change.kind is ChangeKind.BREAKING
    assert change.removed == ("buy_rate",)
    assert change.reason_code == "schema_removed_column"
    assert "removed columns: buy_rate" in change.describe()


def test_type_change_needs_the_threshold_share_of_failures() -> None:
    base = {name: ["x"] * 4 for name in COLUMNS}
    base.update(date=["2024-01-01"] * 4, source_currency=["COP"] * 4, target_currency=["USD"] * 4)
    mostly_bad = pd.DataFrame(
        {**base, "exchange_rate": ["1,5", "2,5", "3,5", "0.1"], "buy_rate": [""] * 4, "sell_rate": [""] * 4},
        dtype="str",
    )
    one_bad = pd.DataFrame(
        {**base, "exchange_rate": ["1,5", "0.2", "0.3", "0.1"], "buy_rate": [""] * 4, "sell_rate": [""] * 4},
        dtype="str",
    )
    header = compare_columns(COLUMNS, RATES)

    breaking = detect_type_changes(header, parse_frame(mostly_bad, RATES), threshold=0.5)
    tolerated = detect_type_changes(header, parse_frame(one_bad, RATES), threshold=0.5)

    assert breaking.kind is ChangeKind.BREAKING
    assert breaking.type_changes == ("exchange_rate",)
    assert breaking.reason_code == "schema_type_change"
    assert breaking.failure_shares["exchange_rate"] == 0.75
    assert tolerated.kind is ChangeKind.UNCHANGED


def test_schema_hash_is_stable_and_order_sensitive() -> None:
    assert schema_hash(["\ufeffa", "B "]) == schema_hash(["a", "b"])
    assert schema_hash(["a", "b"]) != schema_hash(["b", "a"])
    assert normalize_name(" \ufeffColumn ") == "column"
