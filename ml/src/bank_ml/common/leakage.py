"""Leakage guards: columns that are only known after the outcome, and a check that feature pipelines avoid them.

``POST_OUTCOME_COLUMNS`` lists what an intake-time model must never read (the resolution of a complaint, its SLA,
compensation, satisfaction, closing dates). Complaint outcomes appear in gold with an ``outcome_`` prefix, so the
guard also refuses any column starting with ``outcome_``. Session 10b extends the list for the risk estimator
(``days_past_due`` and everything derived from it after the feature snapshot, later statuses).

Every feature pipeline declares the source columns it reads (``SOURCE_COLUMNS``); ``assert_no_leakage`` runs at
dataset build time and a unit test runs it over every declared pipeline and scans the feature modules' source.
"""

import ast
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
    """Every identifier-like word inside the string literals of Python ``source`` (what SQL and column lists name).

    Docstrings are prose, not queries, so they are skipped; comments are not string literals.
    """
    tree = ast.parse(source)
    docstrings = {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef)
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }
    words: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            words.update(re.findall(r"\b[a-z_][a-z0-9_]*\b", node.value.lower()))
    return words
