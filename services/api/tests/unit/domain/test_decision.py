import pytest
from pydantic import ValidationError

from bank_agent.domain.decision import ClauseRef, Decision, DecisionKind, RuleResult
from bank_agent.domain.money import Currency, Money
from bank_agent_builders import decision, rule_result


def test_clause_ref_round_trips_as_a_string() -> None:
    ref = ClauseRef.parse("DSP-CO-2.1@3")
    assert ref.clause_id == "DSP-CO-2.1"
    assert ref.version == 3
    assert ref.family == "DSP"
    assert str(ref) == "DSP-CO-2.1@3"
    assert ref.model_dump_json() == '"DSP-CO-2.1@3"'


@pytest.mark.parametrize(
    "value", ["DSP-CO-2.1", "DSP-CO-2.1@0", "XYZ-CO-1@1", "DSP-BR-1@1", "DSP-CO-@1", "DSP-CO-1@v2"]
)
def test_rejects_malformed_clause_refs(value: str) -> None:
    with pytest.raises(ValidationError):
        ClauseRef.parse(value)


def test_a_passed_rule_has_no_effect_and_a_failed_rule_names_one() -> None:
    with pytest.raises(ValidationError):
        rule_result(passed=True, effect=DecisionKind.DENY)
    with pytest.raises(ValidationError):
        rule_result(passed=False, effect=None)
    with pytest.raises(ValidationError):
        rule_result(passed=True, missing_facts=["transaction_date"])


def test_a_missing_fact_is_a_safe_failure() -> None:
    result = rule_result(passed=False, reason_code="missing_fact", missing_facts=["transaction_date"], params={})
    assert result.effect is DecisionKind.DENY


def test_params_allow_money_but_never_floats() -> None:
    result = rule_result(params={"limit": Money.of("500", Currency.USD), "flag": True, "codes": ["a"]})
    assert RuleResult.model_validate_json(result.model_dump_json()) == result
    with pytest.raises(ValidationError):
        rule_result(params={"ratio": 0.5})


def test_build_derives_the_ordered_clause_union() -> None:
    results = (
        rule_result("AUTH.session_valid", clause="AUTH-ALL-1.1@1"),
        rule_result("DSP.within_window", clause="DSP-MX-2.1@1"),
        rule_result("DSP.status_eligible", clause="AUTH-ALL-1.1@1"),
    )
    built = decision(results=results)
    assert [str(ref) for ref in built.clause_refs] == ["AUTH-ALL-1.1@1", "DSP-MX-2.1@1"]


def test_rejects_inconsistent_clause_refs_and_unknown_decisive_rules() -> None:
    built = decision()
    with pytest.raises(ValidationError):
        Decision.model_validate({**built.model_dump(), "clause_refs": []})
    with pytest.raises(ValidationError):
        Decision.model_validate({**built.model_dump(), "decisive_rule_ids": ["ESC.human_requested"]})


def test_decision_round_trips_through_json() -> None:
    built = decision(DecisionKind.DENY, (rule_result(passed=False),))
    assert Decision.model_validate_json(built.model_dump_json()) == built
