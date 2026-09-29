"""Leakage guards: columns that are only known after the outcome, and a check that feature pipelines avoid them.

``POST_OUTCOME_COLUMNS`` lists what an intake-time model must never read (the resolution of a complaint, its SLA,
compensation, satisfaction, closing dates). Complaint outcomes appear in gold with an ``outcome_`` prefix, so the
guard also refuses any column starting with ``outcome_``.

The risk estimator (session 10b) adds two lists. ``RISK_LABEL_COLUMNS``: days past due and everything derived from
them (any column containing ``days_past_due``) define its label, and customer and product statuses date from the same
single snapshot as the label, so none of them may be a feature. ``PROTECTED_COLUMNS``: protected and proxy attributes
and identifiers (phase 02b, ADR 0021), which no credit feature may read; segment and country are read only as
evaluation slices.

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
RISK_LABEL_COLUMNS: frozenset[str] = frozenset(
    {
        "days_past_due",
        "max_days_past_due",
        "days_past_due_at_snapshot",
        "products_30_plus_days_past_due_at_snapshot",
        "customer_status",
        "product_status",
    }
)
RISK_LABEL_SUBSTRINGS: tuple[str, ...] = ("days_past_due",)
PROTECTED_COLUMNS: frozenset[str] = frozenset(
    {
        "gender",
        "date_of_birth",
        "birth_date",
        "age",
        "marital_status",
        "detected_accent",
        "city",
        "state",
        "postal_code",
        "address",
        "segment",
        "occupation",
        "education_level",
        "first_name",
        "last_name",
        "email",
        "mobile_phone",
        "landline_phone",
        "document_number",
        "document_type",
        "customer_id",
        "product_id",
        "product_number",
    }
)
RISK_DENYLIST: frozenset[str] = POST_OUTCOME_COLUMNS | RISK_LABEL_COLUMNS | PROTECTED_COLUMNS


class LeakageError(ValueError):
    """A feature pipeline references a post-outcome, label-derived, or protected column."""


def leaking(
    columns: Iterable[str], denylist: frozenset[str] = POST_OUTCOME_COLUMNS, substrings: tuple[str, ...] = ()
) -> list[str]:
    """The columns of ``columns`` that are denied (listed, ``outcome_`` prefixed, or containing a substring)."""
    found = []
    for column in columns:
        name = column.lower()
        if name in denylist or name.startswith(POST_OUTCOME_PREFIXES) or any(part in name for part in substrings):
            found.append(column)
    return found


def assert_no_leakage(
    pipeline: str,
    columns: Iterable[str],
    denylist: frozenset[str] = POST_OUTCOME_COLUMNS,
    substrings: tuple[str, ...] = (),
) -> None:
    found = leaking(columns, denylist, substrings)
    if found:
        raise LeakageError(f"{pipeline} reads denied columns: {', '.join(found)}")


def assert_risk_features_clean(pipeline: str, columns: Iterable[str]) -> None:
    """The risk estimator's feature columns: no post-outcome, label-derived, protected, or identifier column."""
    assert_no_leakage(pipeline, columns, RISK_DENYLIST, RISK_LABEL_SUBSTRINGS)


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


def referenced_names(source: str) -> set[str]:
    """Every name, attribute, keyword argument, and quoted identifier-like word in Python ``source``.

    Stricter than ``referenced_identifiers``: a feature module that reads ``profile.max_days_past_due`` is caught
    even though the column never appears in a string. Docstrings are skipped as prose.
    """
    tree = ast.parse(source)
    words = referenced_identifiers(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            words.add(node.id.lower())
        elif isinstance(node, ast.Attribute):
            words.add(node.attr.lower())
        elif isinstance(node, ast.keyword) and node.arg is not None:
            words.add(node.arg.lower())
    return words
