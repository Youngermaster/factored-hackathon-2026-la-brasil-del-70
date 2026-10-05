"""The instrument catalog: every metric the service emits, with its kind, unit, buckets, and attributes.

The OpenTelemetry adapter reads units, descriptions, and histogram buckets from here, so callers pass only the name.
``docs/operations/observability.md`` renders the same list as the signal catalog, and a unit test fails when code
emits a metric that is not listed or an attribute outside its allowlist (attributes are identifiers and codes only,
never text or personal data). The collector exports to Prometheus with unit suffixes: ``bank.turn.duration`` in
seconds becomes ``bank_turn_duration_seconds_bucket``, a counter gains ``_total``.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class Kind(StrEnum):
    COUNTER = "counter"
    HISTOGRAM = "histogram"
    GAUGE = "gauge"


SECONDS_BUCKETS: Final = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 20.0, 30.0, 60.0)
TOKEN_BUCKETS: Final = (16.0, 64.0, 256.0, 1024.0, 4096.0, 16384.0, 65536.0)
COST_BUCKETS: Final = (0.00001, 0.0001, 0.0005, 0.001, 0.005, 0.01, 0.05, 0.1)


@dataclass(frozen=True, slots=True)
class Instrument:
    name: str
    kind: Kind
    unit: str
    description: str
    attributes: frozenset[str]
    buckets: tuple[float, ...] | None = None


def _i(
    name: str, kind: Kind, unit: str, description: str, *attributes: str, buckets: tuple[float, ...] | None = None
) -> Instrument:
    return Instrument(name, kind, unit, description, frozenset(attributes), buckets)


_GENAI = (
    "gen_ai.operation.name",
    "gen_ai.provider.name",
    "gen_ai.request.model",
    "gen_ai.response.model",
    "bank.prompt.id",
)
"""Model call attributes; ``gen_ai.response.model`` is set on success only (the fallback model after a failover)."""
C, H, G = Kind.COUNTER, Kind.HISTOGRAM, Kind.GAUGE

INSTRUMENTS: Final[tuple[Instrument, ...]] = (
    # Language model gateway (phase 08 decorators; GenAI semantic conventions 1.37.0 plus bank attributes).
    _i(
        "gen_ai.client.operation.duration",
        H,
        "s",
        "Duration of one logical model call",
        *_GENAI,
        "error.type",
        buckets=SECONDS_BUCKETS,
    ),
    _i(
        "gen_ai.client.token.usage",
        H,
        "{token}",
        "Tokens per model call",
        *_GENAI,
        "gen_ai.token.type",
        buckets=TOKEN_BUCKETS,
    ),
    _i(
        "bank.llm.cost_usd",
        H,
        "",
        "Cost in USD of one successful model call",
        "gen_ai.response.model",
        "bank.llm.price_basis",
        "bank.prompt.id",
        buckets=COST_BUCKETS,
    ),
    _i("bank.llm.circuit.state", G, "", "Circuit state per provider: 0 closed, 1 half-open, 2 open", "bank.llm.model"),
    _i("bank.llm.budget.refusals", C, "{call}", "Model calls refused by a budget cap", "bank.llm.budget.cap"),
    _i("bank.llm.budget.daily_used_ratio", G, "1", "Share of the daily model budget spent (1 means exhausted)"),
    _i(
        "bank.llm.fallbacks",
        C,
        "{call}",
        "Model calls replaced by the deterministic path",
        "bank.prompt.id",
        "error.type",
        "bank.workflow",
    ),
    # Turns, from the execution record after each turn.
    _i(
        "bank.turn.duration",
        H,
        "s",
        "Turn latency from receipt to the stored record",
        "bank.workflow",
        "bank.outcome",
        buckets=SECONDS_BUCKETS,
    ),
    _i(
        "bank.turn.outcomes",
        C,
        "{turn}",
        "Turns by workflow and outcome",
        "bank.workflow",
        "bank.outcome",
        "bank.language",
    ),
    _i(
        "bank.escalations",
        C,
        "{handoff}",
        "Handoffs by workflow and reason code",
        "bank.workflow",
        "bank.escalation.reason",
    ),
    _i("bank.router.dispatches", C, "{turn}", "Router dispatches by resulting workflow", "bank.workflow"),
    _i(
        "bank.router.switches", C, "{turn}", "Moves from one workflow to another", "bank.workflow.from", "bank.workflow"
    ),
    _i("bank.tool.calls", C, "{call}", "Tool calls by tool and status", "bank.tool", "bank.tool.status"),
    _i("bank.tool.failures", C, "{call}", "Failed tool calls by tool and error code", "bank.tool", "error.type"),
    _i("bank.tool.duration", H, "s", "Tool call latency including retries", "bank.tool", buckets=SECONDS_BUCKETS),
    _i(
        "bank.eligibility.outcomes",
        C,
        "{assessment}",
        "Synthetic eligibility outcomes by product and outcome",
        "bank.credit.product",
        "bank.eligibility.outcome",
    ),
    _i("bank.risk_estimator.failures", C, "{estimate}", "Risk estimates that could not be computed", "bank.workflow"),
    _i(
        "bank.safety.unsafe_blocked",
        C,
        "{message}",
        "Unsafe messages blocked by a runtime detector",
        "bank.detector",
        "bank.workflow",
    ),
    # Reliability and the HTTP layer.
    _i(
        "bank.safety.interventions",
        C,
        "{turn}",
        "Safety interventions by code (injection, fallback, blocks)",
        "bank.intervention",
        "bank.workflow",
    ),
    _i("bank.degradation.level", G, "", "Degradation level, 0 (normal) to 4 (database unavailable)"),
    _i(
        "bank.degradation.component",
        G,
        "",
        "Component state: 0 ok, 1 degraded, 2 unavailable, 3 disabled",
        "bank.component",
    ),
    _i("bank.sessions.active", G, "{session}", "Sessions this process saw within the idle timeout"),
    _i(
        "bank.http.rate_limited", C, "{request}", "Requests refused by a rate limit", "bank.rate_class", "bank.rate_key"
    ),
    _i("bank.database.unavailable", C, "{error}", "Database connection failures translated to 503"),
)

CATALOG: Final[dict[str, Instrument]] = {instrument.name: instrument for instrument in INSTRUMENTS}
