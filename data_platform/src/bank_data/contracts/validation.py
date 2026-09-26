"""Row-level contract validation: every row is either accepted or quarantined with a reason and a column.

The reason codes are stable and documented in ``docs/data/update-policy.md``:

| Code | Meaning |
|---|---|
| ``type_mismatch`` | A non-empty value does not parse as the column type |
| ``null_in_required_column`` | A required column is empty |
| ``value_not_accepted`` | A value is outside the accepted values |
| ``out_of_range`` | A number is outside its range (including survey scores by survey type) |
| ``too_long`` | A string exceeds its dictionary length |
| ``partition_mismatch`` | ``process_date`` differs from the date in the object key |
| ``contract_violation`` | Any other Pandera failure |

Precedence per row: type mismatches first, then failures in column order, then table-level checks.
"""

from dataclasses import dataclass
from datetime import date

import pandas as pd
import pandera.errors

from bank_data.contracts.parsing import ParsedColumn, parse_column
from bank_data.contracts.schemas import SURVEY_SCORE_CHECK, schema_for
from bank_data.contracts.tables import TableSpec

TYPE_MISMATCH = "type_mismatch"
NULL_IN_REQUIRED = "null_in_required_column"
VALUE_NOT_ACCEPTED = "value_not_accepted"
OUT_OF_RANGE = "out_of_range"
TOO_LONG = "too_long"
PARTITION_MISMATCH = "partition_mismatch"
CONTRACT_VIOLATION = "contract_violation"

REASON_CODES = (
    TYPE_MISMATCH,
    NULL_IN_REQUIRED,
    VALUE_NOT_ACCEPTED,
    OUT_OF_RANGE,
    TOO_LONG,
    PARTITION_MISMATCH,
    CONTRACT_VIOLATION,
)


def reason_for_check(check: str) -> str:
    """Map a Pandera check name to a reason code."""
    if check == "not_nullable":
        return NULL_IN_REQUIRED
    if check.startswith("isin"):
        return VALUE_NOT_ACCEPTED
    if check.startswith(("greater_than", "less_than", "in_range")) or check == SURVEY_SCORE_CHECK:
        return OUT_OF_RANGE
    if check.startswith("str_length"):
        return TOO_LONG
    if check.startswith(("dtype", "coerce")):
        return TYPE_MISMATCH
    return CONTRACT_VIOLATION


@dataclass(frozen=True)
class ValidationResult:
    accepted: pd.Series
    """Boolean per row."""
    reason: pd.Series
    """Reason code for rejected rows, null for accepted ones."""
    column: pd.Series
    """Offending column for rejected rows (``*`` for a table-level check)."""
    parsed: dict[str, ParsedColumn]

    @property
    def rejected_count(self) -> int:
        return int((~self.accepted).sum())


def parse_frame(raw: pd.DataFrame, spec: TableSpec) -> dict[str, ParsedColumn]:
    return {column.name: parse_column(raw[column.name], column) for column in spec.columns}


def validate_rows(
    raw: pd.DataFrame,
    spec: TableSpec,
    *,
    partition_date: date | None = None,
    parsed: dict[str, ParsedColumn] | None = None,
) -> ValidationResult:
    """Validate a raw frame that carries every contract column (additive columns already removed)."""
    parsed = parsed if parsed is not None else parse_frame(raw, spec)
    index = raw.index
    reason = pd.Series(pd.NA, index=index, dtype="object")
    column = pd.Series(pd.NA, index=index, dtype="object")

    def assign(mask: pd.Series, code: str, name: str) -> None:
        target = mask & reason.isna()
        reason[target] = code
        column[target] = name

    for spec_column in spec.columns:
        assign(parsed[spec_column.name].failed, TYPE_MISMATCH, spec_column.name)

    typed = pd.DataFrame({name: item.values for name, item in parsed.items()}, index=index)
    try:
        schema_for(spec.name).validate(typed, lazy=True)
    except pandera.errors.SchemaErrors as errors:
        cases = errors.failure_cases
        order = {name: position for position, name in enumerate(spec.column_names)}
        cases = cases.assign(_order=cases["column"].map(order).fillna(len(order)))
        cases = cases.sort_values(["_order", "check_number"], kind="stable", na_position="last")
        cases = cases.assign(
            _code=cases["check"].astype(str).map(reason_for_check),
            _name=cases["column"].map(lambda value: value if isinstance(value, str) else "main_score"),
        )
        whole_column = cases[cases["index"].isna()]
        for case in whole_column.itertuples(index=False):
            assign(pd.Series(True, index=index), str(case._code), str(case._name))
        per_row = cases[cases["index"].notna()].drop_duplicates("index", keep="first")
        if not per_row.empty:
            codes = pd.Series(per_row["_code"].to_numpy(), index=per_row["index"].astype("int64").to_numpy())
            names = pd.Series(per_row["_name"].to_numpy(), index=codes.index)
            codes = codes.reindex(index)
            names = names.reindex(index)
            target = codes.notna() & reason.isna()
            reason[target] = codes[target]
            column[target] = names[target]

    if partition_date is not None and "process_date" in parsed:
        process_dates = parsed["process_date"].values
        mismatch = process_dates.notna() & (process_dates.dt.date != partition_date)
        assign(mismatch.astype(bool), PARTITION_MISMATCH, "process_date")

    return ValidationResult(accepted=reason.isna(), reason=reason, column=column, parsed=parsed)
