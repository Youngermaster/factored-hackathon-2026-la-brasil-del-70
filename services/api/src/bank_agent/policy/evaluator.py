"""The policy evaluator: a pure function from an evaluation request and a pack to a ``Decision``.

Which rules run: the bound rules of every clause bound to the workflow state (common clauses included), so
the rules and the customer-facing explanations come from the same files. ELG rules are left to the synthetic
eligibility service. Order: by family (AUTH, PRV, SCOPE, ACC, CRD, DSP, CRE, ESC), then registration order.

Precedence among failed rules:

1. An AUTH failure decides first, deny before step-up: insufficient authentication always yields ``deny`` or
   ``require_step_up``, whatever the other facts.
2. Then ``refuse`` (a privacy or ownership failure), ``escalate`` (any escalation trigger), ``deny``,
   ``require_step_up`` from other rules, ``abstain``, and ``clarify``. Escalation therefore dominates denial and
   every automatic resolution, and deny overrides allow.
3. With every rule passed, an action that needs confirmation and has no ``confirmed_at`` gives
   ``require_confirmation``; otherwise ``allow``.
"""

from bank_agent.domain.decision import Decision, DecisionKind, RuleResult
from bank_agent.domain.locale import Language
from bank_agent.domain.policy import ActionRequirement
from bank_agent.policy.facts import EvaluationRequest
from bank_agent.policy.pack import PolicyPack
from bank_agent.policy.rules import CONVERSATION_RULES, RuleContext
from bank_agent.policy.selection import merge_params, refs, rule_clauses

FAMILY_ORDER = ("AUTH", "PRV", "SCOPE", "ACC", "CRD", "DSP", "CRE", "ESC")
AUTH_PRECEDENCE = (DecisionKind.DENY, DecisionKind.REQUIRE_STEP_UP)
EFFECT_PRECEDENCE = (
    DecisionKind.REFUSE,
    DecisionKind.ESCALATE,
    DecisionKind.DENY,
    DecisionKind.REQUIRE_STEP_UP,
    DecisionKind.ABSTAIN,
    DecisionKind.CLARIFY,
)
_REGISTRATION = {rule_id: index for index, rule_id in enumerate(CONVERSATION_RULES.order())}


def rule_order_key(rule_id: str) -> tuple[int, int]:
    return FAMILY_ORDER.index(rule_id.split(".", 1)[0]), _REGISTRATION[rule_id]


def rules_for(request: EvaluationRequest, pack: PolicyPack) -> tuple[str, ...]:
    """The conversation rules bound to the request's workflow state, in evaluation order."""
    clause_ids = pack.bindings.clause_ids(request.workflow, request.state, request.facts.jurisdiction)
    bound = {
        rule_id
        for clause_id in clause_ids
        for rule_id in pack.get_clause(clause_id, Language.ES).metadata.bound_rules
        if rule_id in CONVERSATION_RULES
    }
    return tuple(sorted(bound, key=rule_order_key))


def combine(
    results: tuple[RuleResult, ...], request: EvaluationRequest, requirement: ActionRequirement | None
) -> tuple[DecisionKind, tuple[str, ...]]:
    """The decision kind and the decisive rule ids, by the precedence in the module docstring."""
    failed = [result for result in results if not result.passed]
    auth = [result for result in failed if result.rule_id.startswith("AUTH.")]
    for pool, order in ((auth, AUTH_PRECEDENCE), (failed, EFFECT_PRECEDENCE)):
        for effect in order:
            decisive = tuple(result.rule_id for result in pool if result.effect is effect)
            if decisive:
                return effect, decisive
    action = request.action
    needs_confirmation = requirement is not None and requirement.requires_confirmation
    if action is not None and needs_confirmation and action.confirmed_at is None:
        return DecisionKind.REQUIRE_CONFIRMATION, ()
    return DecisionKind.ALLOW, ()


def evaluate(request: EvaluationRequest, pack: PolicyPack) -> Decision:
    """Evaluate ``request`` against ``pack``. Deterministic, with no I/O and no clock.

    Raises ``PolicyBindingMissingError`` for a state the bindings do not know (a programming error).
    """
    binding = pack.bindings.binding(request.workflow, request.state)
    requirement = pack.action_requirements(request.action.action) if request.action is not None else None
    current = pack.list_clauses(language=Language.ES, jurisdiction=request.facts.jurisdiction)
    results: list[RuleResult] = []
    for rule_id in rules_for(request, pack):
        clauses = rule_clauses(current, rule_id, request.facts.jurisdiction)
        context = RuleContext(
            request=request, params=merge_params(clauses), state_auth=binding.auth, requirement=requirement
        )
        results.append(CONVERSATION_RULES[rule_id].run(context, refs(clauses)))
    rule_results = tuple(results)
    kind, decisive = combine(rule_results, request, requirement)
    return Decision.build(
        state=request.state,
        kind=kind,
        rule_results=rule_results,
        policy_pack_version=pack.version,
        action=request.action.action if request.action is not None else None,
        decisive_rule_ids=decisive,
    )
