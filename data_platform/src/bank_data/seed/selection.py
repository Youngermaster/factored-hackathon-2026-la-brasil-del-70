"""Deterministic customer selection: personas first, then coverage, then a seeded-hash fill up to the target.

Candidates are active customers with a phone on file (document identification needs its last four digits),
ordered by ``md5(seed || customer_id)``; each persona takes the first candidate no other persona took.
"""

from dataclasses import dataclass, field
from datetime import date

import duckdb

from bank_data.errors import ConfigurationError
from bank_data.seed.config import PersonaFile
from bank_data.seed.criteria import CRITERIA

SEGMENTS = ("premium", "plus", "basic", "student")
COUNTRIES = ("MX", "CO", "AR")
_CANDIDATES = (
    "SELECT c.customer_id FROM customers_serving c WHERE c.customer_status = 'active' "
    "AND c.mobile_phone IS NOT NULL AND length(regexp_replace(c.mobile_phone, '[^0-9]', '', 'g')) >= 4 "
    "AND ($country IS NULL OR c.country = $country) AND ($segment IS NULL OR c.segment = $segment) AND ({predicate}) "
    "ORDER BY md5($seed || c.customer_id) LIMIT $limit"
)


@dataclass
class Selection:
    personas: dict[str, str] = field(default_factory=dict)
    """Persona id to customer id."""
    customers: list[str] = field(default_factory=list)
    """Every selected customer id, personas first, in selection order."""

    def add(self, customer_id: str) -> None:
        if customer_id not in self.customers:
            self.customers.append(customer_id)


def _candidates(
    connection: duckdb.DuckDBPyConnection,
    predicate: str,
    *,
    seed: str,
    snapshot: date,
    country: str | None = None,
    segment: str | None = None,
    limit: int = 200,
) -> list[str]:
    parameters = {"seed": seed, "snapshot": snapshot, "country": country, "segment": segment, "limit": limit}
    sql = _CANDIDATES.format(predicate=predicate)
    if "$snapshot" not in sql:
        parameters.pop("snapshot")
    return [row[0] for row in connection.execute(sql, parameters).fetchall()]


def _counts(connection: duckdb.DuckDBPyConnection, selection: Selection, column: str) -> dict[str, int]:
    if not selection.customers:
        return {}
    rows = connection.execute(
        f"SELECT {column}, count(*) FROM customers_serving WHERE customer_id IN "  # noqa: S608  # nosec B608 (fixed column)
        f"(SELECT unnest($ids)) GROUP BY 1",
        {"ids": selection.customers},
    ).fetchall()
    return {str(key): int(count) for key, count in rows}


def select_customers(
    connection: duckdb.DuckDBPyConnection, personas: PersonaFile, *, target: int, snapshot: date
) -> Selection:
    selection = Selection()
    for persona in personas.customers:
        predicate = CRITERIA.get(persona.criterion)
        if predicate is None:
            raise ConfigurationError(f"persona {persona.id} names an unknown criterion {persona.criterion}")
        pool = _candidates(connection, predicate, seed=personas.seed, snapshot=snapshot, country=persona.country)
        found = [candidate for candidate in pool if candidate not in selection.customers]
        if not found:
            raise ConfigurationError(f"no customer matches persona {persona.id} ({persona.criterion})")
        selection.personas[persona.id] = found[0]
        selection.add(found[0])
    coverage = personas.coverage
    for country in COUNTRIES:
        missing = coverage.min_customers_per_country - _counts(connection, selection, "country").get(country, 0)
        for candidate in _candidates(connection, "TRUE", seed=personas.seed, snapshot=snapshot, country=country):
            if missing <= 0:
                break
            if candidate not in selection.customers:
                selection.add(candidate)
                missing -= 1
    if coverage.every_segment:
        for segment in SEGMENTS:
            if _counts(connection, selection, "segment").get(segment, 0) == 0:
                found = _candidates(connection, "TRUE", seed=personas.seed, snapshot=snapshot, segment=segment, limit=1)
                if found:
                    selection.add(found[0])
    if len(selection.customers) < target:
        for candidate in _candidates(connection, "TRUE", seed=personas.seed, snapshot=snapshot, limit=target * 2):
            if len(selection.customers) >= target:
                break
            selection.add(candidate)
    return selection
