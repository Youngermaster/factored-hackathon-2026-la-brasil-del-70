"""Strict parsing of raw CSV strings into typed pandas columns.

Every value arrives as a string. Empty or whitespace-only strings are missing values, not failures. A
non-empty value that does not match the column type is a failure; the caller turns failures into
``type_mismatch`` quarantine rows (or, above a threshold, a breaking type change for the whole batch).
Nothing is coerced leniently: ``nan``, ``inf``, ``1,5``, and ``15/01/2024`` are all failures.
"""

from dataclasses import dataclass

import pandas as pd

from bank_data.contracts.tables import ColumnSpec, DType

_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_INTEGER = r"[+-]?\d+(?:\.0+)?"
_DATE = r"\d{4}-\d{2}-\d{2}"
_TIMESTAMP = r"\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:\.\d{1,9})?"
_TIME = r"(?:[01]\d|2[0-3]):[0-5]\d(?::[0-5]\d)?"
_BOOLEANS = {"true": True, "false": False}

PANDAS_DTYPES: dict[DType, str] = {
    "string": "str",
    "integer": "Int64",
    "decimal": "float64",
    "date": "datetime64[ns]",
    "timestamp": "datetime64[ns]",
    "boolean": "boolean",
    "time": "str",
}


@dataclass(frozen=True)
class ParsedColumn:
    values: pd.Series
    """Typed values; missing and failed values are null."""
    failed: pd.Series
    """True where a non-empty raw value did not parse."""
    present: pd.Series
    """True where the raw value was non-empty."""


def parse_column(raw: pd.Series, column: ColumnSpec) -> ParsedColumn:
    """Parse one raw column (strings or nulls) according to ``column.dtype``."""
    stripped = raw.astype("str").str.strip()
    present = (stripped.notna() & (stripped != "")).astype(bool)
    candidates = stripped.where(present)
    dtype = column.dtype
    if dtype == "string":
        return ParsedColumn(values=candidates, failed=pd.Series(False, index=raw.index), present=present)
    if dtype == "boolean":
        mapped = candidates.str.lower().map(_BOOLEANS)
        failed = present & mapped.isna()
        return ParsedColumn(values=mapped.astype("boolean"), failed=failed, present=present)
    pattern = {
        "integer": _INTEGER,
        "decimal": _NUMBER,
        "date": _DATE,
        "timestamp": _TIMESTAMP,
        "time": _TIME,
    }[dtype]
    matches = candidates.str.fullmatch(pattern).fillna(False).astype(bool) & present
    usable = candidates.where(matches)
    typed: pd.Series
    if dtype in ("integer", "decimal"):
        numbers = pd.to_numeric(usable, errors="coerce")
        typed = numbers.round().astype("Int64") if dtype == "integer" else numbers.astype("float64")
        failed = present & ~matches
    elif dtype in ("date", "timestamp"):
        typed = pd.to_datetime(usable, errors="coerce", format="ISO8601").astype("datetime64[ns]")
        failed = present & (~matches | typed.isna())
        typed = typed.where(~failed)
    else:
        typed = usable
        failed = present & ~matches
    return ParsedColumn(values=typed, failed=failed.astype(bool), present=present)


def failure_share(parsed: ParsedColumn) -> float:
    """The share of non-empty values that failed to parse (0 when the column is empty)."""
    present = int(parsed.present.sum())
    return 0.0 if present == 0 else int(parsed.failed.sum()) / present
