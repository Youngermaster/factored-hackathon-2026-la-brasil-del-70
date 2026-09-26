"""Pandera schemas built from the table specs: dtypes, nullability, accepted values, ranges, lengths.

Schemas are strict (a column outside the contract fails) and validate the typed frame produced by
``bank_data.contracts.parsing``. Additive columns never reach them: the schema-evolution detector removes
them first and bronze keeps them as nullable strings.
"""

from functools import cache

import pandas as pd
import pandera.pandas as pa

from bank_data.contracts.parsing import PANDAS_DTYPES
from bank_data.contracts.tables import (
    CONTRACT_VERSION,
    SATISFACTION_SURVEYS,
    SURVEY_SCORE_RANGES,
    ColumnSpec,
    TableSpec,
    table_spec,
)

SURVEY_SCORE_CHECK = "survey_score_range"


def _column_checks(column: ColumnSpec) -> list[pa.Check]:
    checks: list[pa.Check] = []
    if column.accepted is not None:
        checks.append(pa.Check.isin(list(column.accepted)))
    if column.minimum is not None:
        checks.append(pa.Check.ge(float(column.minimum)))
    if column.maximum is not None:
        checks.append(pa.Check.le(float(column.maximum)))
    if column.max_length is not None:
        checks.append(pa.Check.str_length(max_value=column.max_length))
    return checks


def survey_scores_in_range(frame: pd.DataFrame) -> pd.Series:
    """``main_score`` must fall in the range of its ``survey_type``; rows with a missing part pass here."""
    lower = frame["survey_type"].map({kind: bounds[0] for kind, bounds in SURVEY_SCORE_RANGES.items()})
    upper = frame["survey_type"].map({kind: bounds[1] for kind, bounds in SURVEY_SCORE_RANGES.items()})
    score = frame["main_score"].astype("float64")
    known = score.notna() & lower.notna()
    inside = (score >= lower.astype("float64")) & (score <= upper.astype("float64"))
    return (~known | inside).astype(bool)


def build_schema(spec: TableSpec) -> pa.DataFrameSchema:
    columns = {
        column.name: pa.Column(
            PANDAS_DTYPES[column.dtype],
            nullable=column.nullable,
            checks=_column_checks(column),
            required=True,
            name=column.name,
        )
        for column in spec.columns
    }
    checks: list[pa.Check] = []
    if spec.name == SATISFACTION_SURVEYS.name:
        checks.append(pa.Check(survey_scores_in_range, name=SURVEY_SCORE_CHECK))
    return pa.DataFrameSchema(
        columns,
        checks=checks,
        strict=True,
        coerce=False,
        name=f"{spec.name}@{CONTRACT_VERSION}",
    )


@cache
def schema_for(table: str) -> pa.DataFrameSchema:
    return build_schema(table_spec(table))
