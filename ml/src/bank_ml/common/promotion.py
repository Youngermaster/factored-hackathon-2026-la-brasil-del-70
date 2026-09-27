"""Promotion: move the ``champion`` alias to the ``candidate`` only when the candidate wins on the primary metric
and loses no more than a stated amount on each guard metric; record the decision either way.

The comparison uses the metrics stored in each version's manifest (dev and test, written by ``train`` and
``evaluate``). Without a champion, the candidate is compared with the rule baseline's metrics from the same
evaluation. The record lists every metric compared, the decision with reasons, who approved, when, and the commit.
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime

from pydantic import JsonValue

from bank_agent.adapters.models.registry import FilesystemModelStore


@dataclass(frozen=True)
class Guard:
    metric: str
    max_loss: float
    higher_is_better: bool = True


@dataclass(frozen=True)
class PromotionRule:
    primary: str
    guards: tuple[Guard, ...] = ()
    higher_is_better: bool = True


@dataclass(frozen=True)
class Decision:
    promote: bool
    reasons: tuple[str, ...]
    compared: Mapping[str, Mapping[str, float]] = field(default_factory=dict)


def floats(value: object) -> dict[str, float]:
    """The numeric entries of a manifest mapping (anything else is ignored)."""
    if not isinstance(value, dict):
        return {}
    return {
        str(key): float(item)
        for key, item in value.items()
        if isinstance(item, int | float) and not isinstance(item, bool)
    }


def _gain(candidate: float, reference: float, higher_is_better: bool) -> float:
    return candidate - reference if higher_is_better else reference - candidate


def decide(candidate: Mapping[str, float], reference: Mapping[str, float], rule: PromotionRule) -> Decision:
    reasons: list[str] = []
    compared: dict[str, dict[str, float]] = {}
    metrics = (rule.primary, *(guard.metric for guard in rule.guards))
    missing = [metric for metric in metrics if metric not in candidate or metric not in reference]
    if missing:
        return Decision(False, (f"metrics missing: {', '.join(missing)}",))
    for metric in metrics:
        compared[metric] = {"candidate": candidate[metric], "reference": reference[metric]}
    gain = _gain(candidate[rule.primary], reference[rule.primary], rule.higher_is_better)
    ok = gain > 0
    reasons.append(f"{rule.primary}: {'better' if ok else 'not better'} by {gain:+.4f}")
    for guard in rule.guards:
        loss = -_gain(candidate[guard.metric], reference[guard.metric], guard.higher_is_better)
        within = loss <= guard.max_loss
        ok = ok and within
        reasons.append(f"{guard.metric}: loss {loss:+.4f} {'within' if within else 'above'} {guard.max_loss:.4f}")
    return Decision(ok, tuple(reasons), compared)


def promote(
    store: FilesystemModelStore,
    name: str,
    rule: PromotionRule,
    *,
    approved_by: str,
    now: datetime,
    commit: str,
    baseline_key: str = "baseline_metrics",
) -> Decision:
    """Compare ``name@candidate`` with ``name@champion`` (or the stored baseline) and move ``champion`` if it wins."""
    candidate_alias = store.alias(name, "candidate")
    if candidate_alias is None:
        return Decision(False, (f"{name} has no candidate; run train first",))
    candidate = store.registry.resolve(name, "candidate")
    champion_alias = store.alias(name, "champion")
    candidate_metrics = floats(candidate.metadata.get("metrics"))
    if champion_alias is not None:
        champion = store.registry.resolve(name, "champion")
        if champion.ref.version == candidate.ref.version:
            return Decision(False, ("the candidate is already the champion",))
        reference = floats(champion.metadata.get("metrics"))
        against = str(champion.ref)
    else:
        reference = floats(candidate.metadata.get(baseline_key))
        against = str(candidate.metadata.get("baseline", "baseline"))
    decision = decide(candidate_metrics, reference, rule)
    record: dict[str, JsonValue] = {
        "approved_by": approved_by,
        "decided_at": now.isoformat(),
        "git_sha": commit,
        "candidate": str(candidate.ref),
        "compared_with": against,
        "decision": "promoted" if decision.promote else "refused",
        "reasons": list[JsonValue](decision.reasons),
        "metrics_compared": {metric: dict(values.items()) for metric, values in decision.compared.items()},
    }
    if decision.promote:
        store.set_alias(name, "champion", candidate.ref.version, record)
    else:
        store.log_decision(name, {"alias": "champion", "version": candidate.ref.version, **record})
    return decision
