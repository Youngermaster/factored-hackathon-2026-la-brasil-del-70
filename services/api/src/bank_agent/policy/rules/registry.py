"""The rule registry: pure functions registered by id and version, with the parameters and reasons they use.

A rule function takes a context and returns a ``Verdict``; the registry turns it into a ``RuleResult`` with the
rule id, version, parameters used, and the clause references of the clauses that bind the rule. Registration
order is the evaluation order, so importing ``bank_agent.policy.rules`` fixes it once.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any

from bank_agent.domain.decision import ClauseRef, DecisionKind, ParamValue, RuleResult
from bank_agent.domain.errors import PolicyPackInvalidError
from bank_agent.domain.money import Money

ParamType = type[int] | type[bool] | type[str] | type[Money] | type[list[Any]]


@dataclass(frozen=True)
class Verdict:
    """What a rule decided. A failure names its effect; missing facts make a failure safe, never an error."""

    passed: bool
    reason_code: str
    effect: DecisionKind | None = None
    params: Mapping[str, ParamValue] = field(default_factory=dict)
    missing_facts: tuple[str, ...] = ()


def ok(reason_code: str, **params: ParamValue) -> Verdict:
    return Verdict(passed=True, reason_code=reason_code, params=params)


def fail(effect: DecisionKind, reason_code: str, *, missing: tuple[str, ...] = (), **params: ParamValue) -> Verdict:
    return Verdict(passed=False, reason_code=reason_code, effect=effect, params=params, missing_facts=missing)


@dataclass(frozen=True)
class RuleSpec[C]:
    rule_id: str
    version: int
    params: Mapping[str, ParamType]
    reason_codes: tuple[str, ...]
    missing_facts: tuple[str, ...]
    function: Callable[[C], Verdict]

    def run(self, context: C, clause_refs: tuple[ClauseRef, ...]) -> RuleResult:
        verdict = self.function(context)
        if verdict.reason_code not in self.reason_codes:
            raise PolicyPackInvalidError(f"{self.rule_id} returned an undeclared reason code")
        return RuleResult(
            rule_id=self.rule_id,
            rule_version=self.version,
            passed=verdict.passed,
            effect=verdict.effect,
            reason_code=verdict.reason_code,
            params=dict(verdict.params),
            clause_refs=clause_refs,
            missing_facts=verdict.missing_facts,
        )


class RuleRegistry[C]:
    """An ordered set of rules sharing one context type."""

    def __init__(self, prefixes: tuple[str, ...]) -> None:
        self._prefixes = prefixes
        self._specs: dict[str, RuleSpec[C]] = {}

    def rule(
        self,
        rule_id: str,
        *,
        version: int,
        reasons: tuple[str, ...],
        params: Mapping[str, ParamType] | None = None,
        missing_facts: tuple[str, ...] = (),
    ) -> Callable[[Callable[[C], Verdict]], Callable[[C], Verdict]]:
        if not rule_id.startswith(self._prefixes) or rule_id in self._specs:
            raise ValueError(f"cannot register {rule_id}")

        def register(function: Callable[[C], Verdict]) -> Callable[[C], Verdict]:
            spec = RuleSpec(rule_id, version, dict(params or {}), reasons, missing_facts, function)
            self._specs[rule_id] = spec
            return function

        return register

    def __contains__(self, rule_id: object) -> bool:
        return rule_id in self._specs

    def __getitem__(self, rule_id: str) -> RuleSpec[C]:
        return self._specs[rule_id]

    def specs(self) -> tuple[RuleSpec[C], ...]:
        return tuple(self._specs.values())

    def order(self) -> tuple[str, ...]:
        return tuple(self._specs)


def typed_param[T](params: Mapping[str, ParamValue], name: str, kind: type[T]) -> T:
    """Read a parameter the loader has already checked; a wrong type is a pack error, never customer input."""
    value = params.get(name)
    if not isinstance(value, kind) or (kind is int and isinstance(value, bool)):
        raise PolicyPackInvalidError(f"parameter {name} is missing or has the wrong type")
    return value


def str_list(params: Mapping[str, ParamValue], name: str) -> tuple[str, ...]:
    return tuple(str(item) for item in typed_param(params, name, list))
