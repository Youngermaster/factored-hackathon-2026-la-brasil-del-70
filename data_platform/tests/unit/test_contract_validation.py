from datetime import date

import pandas as pd
import pytest

from bank_data.contracts.parsing import parse_column
from bank_data.contracts.schemas import build_schema, survey_scores_in_range
from bank_data.contracts.tables import TABLES, ColumnSpec, table_spec
from bank_data.contracts.validation import (
    CONTRACT_VIOLATION,
    NULL_IN_REQUIRED,
    OUT_OF_RANGE,
    PARTITION_MISMATCH,
    TOO_LONG,
    TYPE_MISMATCH,
    VALUE_NOT_ACCEPTED,
    reason_for_check,
    validate_rows,
)


def _raw(values: list[str | None]) -> pd.Series:
    return pd.Series(values, dtype="str")


@pytest.mark.parametrize(
    ("dtype", "raw", "expected", "failed"),
    [
        ("integer", ["701.0", "5", " 12 ", "", "7.5", "nan"], [701, 5, 12, None, None, None], [0, 0, 0, 0, 1, 1]),
        (
            "decimal",
            ["1.50", "9.7e-05", "-3", "1,5", "inf", None],
            [1.5, 0.000097, -3.0, None, None, None],
            [0, 0, 0, 1, 1, 0],
        ),
        ("boolean", ["True", "false", "yes", ""], [True, False, None, None], [0, 0, 1, 0]),
        ("date", ["2024-01-15", "15/01/2024", "2024-02-30"], ["2024-01-15", None, None], [0, 1, 1]),
        ("time", ["09:30:00", "24:00:00", "08:15"], ["09:30:00", None, "08:15"], [0, 1, 0]),
    ],
)
def test_parses_strictly_and_marks_failures(
    dtype: str, raw: list[str | None], expected: list[object], failed: list[int]
) -> None:
    parsed = parse_column(_raw(raw), ColumnSpec("value", dtype))  # type: ignore[arg-type]

    assert [bool(flag) for flag in parsed.failed] == [bool(flag) for flag in failed]
    for value, want in zip(parsed.values, expected, strict=True):
        if want is None:
            assert pd.isna(value)
        elif dtype == "date":
            assert value.date().isoformat() == want
        elif dtype == "decimal":
            assert value == pytest.approx(want)
        else:
            assert value == want


def test_timestamps_accept_iso_forms_only() -> None:
    parsed = parse_column(
        _raw(["2024-01-15 12:24:10", "2024-01-15T12:24:10", "2024-01-15", "x"]), ColumnSpec("t", "timestamp")
    )
    assert list(parsed.failed) == [False, False, True, True]
    assert parsed.values.iloc[0] == pd.Timestamp("2024-01-15 12:24:10")


def test_every_table_spec_builds_a_strict_schema() -> None:
    for spec in TABLES:
        schema = build_schema(spec)
        assert schema.strict is True
        assert list(schema.columns) == list(spec.column_names)


def _exchange_rows(**overrides: str) -> pd.DataFrame:
    row = {
        "date": "2024-01-01",
        "source_currency": "COP",
        "target_currency": "USD",
        "exchange_rate": "0.00025",
        "buy_rate": "",
        "sell_rate": "",
        "source": "Reuters",
    }
    row.update(overrides)
    return pd.DataFrame([row], dtype="str")


@pytest.mark.parametrize(
    ("overrides", "reason", "column"),
    [
        ({}, None, None),
        ({"exchange_rate": "abc"}, TYPE_MISMATCH, "exchange_rate"),
        ({"exchange_rate": ""}, NULL_IN_REQUIRED, "exchange_rate"),
        ({"source_currency": "EUR"}, VALUE_NOT_ACCEPTED, "source_currency"),
        ({"exchange_rate": "-1"}, OUT_OF_RANGE, "exchange_rate"),
        ({"source": "x" * 51}, TOO_LONG, "source"),
    ],
)
def test_rows_are_accepted_or_quarantined_with_a_reason_and_column(
    overrides: dict[str, str], reason: str | None, column: str | None
) -> None:
    result = validate_rows(_exchange_rows(**overrides), table_spec("daily_exchange_rates"))

    assert bool(result.accepted.iloc[0]) is (reason is None)
    if reason is not None:
        assert result.reason.iloc[0] == reason
        assert result.column.iloc[0] == column


def test_type_mismatch_takes_precedence_over_later_failures() -> None:
    frame = _exchange_rows(exchange_rate="abc", source_currency="EUR")
    result = validate_rows(frame, table_spec("daily_exchange_rates"))
    assert (result.reason.iloc[0], result.column.iloc[0]) == (TYPE_MISMATCH, "exchange_rate")


def test_survey_scores_are_checked_by_survey_type() -> None:
    frame = pd.DataFrame(
        {"survey_type": ["CSAT", "CSAT", "NPS", "CES", None], "main_score": pd.array([5, 6, 10, 7, 99], dtype="Int64")}
    )
    assert list(survey_scores_in_range(frame)) == [True, False, True, True, True]


def test_partition_mismatch_is_quarantined() -> None:
    spec = table_spec("complaints")
    row = dict.fromkeys(spec.column_names, "")
    row.update(
        complaint_id="CMP-1",
        creation_date="2024-01-02 10:00:00",
        process_date="2024-01-02",
        customer_id="CLI-1",
        case_type="Claim",
        category="Fees",
        reception_channel="App",
        description="texto",
        priority="Low",
        status="Open",
        sla_breached="False",
        is_repeat_complainer="False",
    )
    frame = pd.DataFrame([row], dtype="str")

    assert bool(validate_rows(frame, spec, partition_date=date(2024, 1, 2)).accepted.iloc[0]) is True
    result = validate_rows(frame, spec, partition_date=date(2024, 1, 3))
    assert (result.reason.iloc[0], result.column.iloc[0]) == (PARTITION_MISMATCH, "process_date")


@pytest.mark.parametrize(
    ("check", "reason"),
    [
        ("not_nullable", NULL_IN_REQUIRED),
        ("isin(['A'])", VALUE_NOT_ACCEPTED),
        ("greater_than_or_equal_to(0)", OUT_OF_RANGE),
        ("less_than_or_equal_to(5)", OUT_OF_RANGE),
        ("survey_score_range", OUT_OF_RANGE),
        ("str_length(None, 10)", TOO_LONG),
        ("dtype('Int64')", TYPE_MISMATCH),
        ("something_else", CONTRACT_VIOLATION),
    ],
)
def test_maps_pandera_checks_to_reason_codes(check: str, reason: str) -> None:
    assert reason_for_check(check) == reason
