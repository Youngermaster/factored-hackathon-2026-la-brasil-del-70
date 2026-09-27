"""Leakage guards: columns that are only known after the outcome, and a check that feature pipelines avoid them.

``POST_OUTCOME_COLUMNS`` lists what an intake-time model must never read (the resolution of a complaint, its SLA,
compensation, satisfaction, closing dates). Complaint outcomes appear in gold with an ``outcome_`` prefix, so the
guard also refuses any column starting with ``outcome_``. Session 10b extends the list for the risk estimator
(``days_past_due`` and everything derived from it after the feature snapshot, later statuses).

Every feature pipeline declares the source columns it reads (``SOURCE_COLUMNS``); ``assert_no_leakage`` runs at
dataset build time and a unit test runs it over every declared pipeline and scans the feature modules' source.
"""

import re
from collections.abc import Iterable

POST_OUTCOME_COLUMNS: frozenset[str] = frozenset(
    {
        "status",
        "resolution",
        "resolution_date",
        "closing_date",
        "resolution_days",
        "sla_breached",
        "compensation_granted",
        "resolution_satisfaction",
        "was_resolved",
    }
)
POST_OUTCOME_PREFIXES: tuple[str, ...] = ("outcome_",)


class LeakageError(ValueError):
    """A feature pipeline references a post-outcome column."""


def leaking(columns: Iterable[str], denylist: frozenset[str] = POST_OUTCOME_COLUMNS) -> list[str]:
    """The columns of ``columns`` that are denied, in order."""
    return [
        column for column in columns if column.lower() in denylist or column.lower().startswith(POST_OUTCOME_PREFIXES)
    ]


def assert_no_leakage(pipeline: str, columns: Iterable[str], denylist: frozenset[str] = POST_OUTCOME_COLUMNS) -> None:
    found = leaking(columns, denylist)
    if found:
        raise LeakageError(f"{pipeline} reads post-outcome columns: {', '.join(found)}")


def referenced_identifiers(source: str) -> set[str]:
    """Every quoted identifier-like string in Python ``source`` (what a SQL query or a column list names)."""
    return set(re.findall(r"\b[a-z_][a-z0-9_]*\b", " ".join(re.findall(r"[\"']([^\"']*)[\"']", source))))
