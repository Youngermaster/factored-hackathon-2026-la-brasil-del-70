import pytest
from pydantic import ValidationError

from bank_agent.domain.actions import ActionKind, ActionStatus
from bank_agent.domain.errors import InvalidHandoffTransitionError
from bank_agent.domain.handoff import ActionTaken, Handoff, HandoffOutcomeCode, HandoffRecord, HandoffStatus
from bank_agent.domain.identifiers import StaffId
from bank_agent.domain.locale import Language
from bank_agent_builders import T0, handoff

AGENT = StaffId("agent-1")


def _action(**overrides: object) -> dict[str, object]:
    fields: dict[str, object] = {
        "action": ActionKind.CREATE_DISPUTE_CASE,
        "target": "transactions:TXN-A-0001",
        "confirmed": True,
        "status": ActionStatus.EXECUTED,
        "verification": "verified",
        "evidence": "dispute_cases:case-000001",
    }
    return {**fields, **overrides}


def test_builds_a_valid_handoff() -> None:
    document = handoff()
    assert document.schema_version == "1.0.0"
    assert document.customer_ref == "CUS-A-0001"


def test_rejects_a_verified_fact_without_a_source_reference() -> None:
    with pytest.raises(ValidationError):
        handoff(verified_facts=[{"fact": "Purchase of 1250.00 MXN"}])
    with pytest.raises(ValidationError):
        handoff(verified_facts=[{"fact": "Purchase of 1250.00 MXN", "source": None}])


def test_rejects_an_unverified_action_marked_as_verified() -> None:
    with pytest.raises(ValidationError, match="only an executed action can be verified"):
        ActionTaken.model_validate(_action(status=ActionStatus.UNKNOWN))
    with pytest.raises(ValidationError, match="evidence"):
        ActionTaken.model_validate(_action(evidence=None))


def test_every_action_has_a_verification_status() -> None:
    fields = _action()
    del fields["verification"]
    with pytest.raises(ValidationError):
        ActionTaken.model_validate(fields)


def test_an_executed_action_must_have_been_confirmed() -> None:
    with pytest.raises(ValidationError, match="confirmed"):
        ActionTaken.model_validate(_action(confirmed=False))
    failed = ActionTaken.model_validate(
        _action(status=ActionStatus.FAILED, verification="not_verified", confirmed=True)
    )
    assert failed.evidence is not None


@pytest.mark.parametrize("field", ["transcript", "messages", "conversation_history", "raw_text"])
def test_rejects_raw_transcript_fields(field: str) -> None:
    with pytest.raises(ValidationError):
        handoff(**{field: "Cliente: hola\nAgente: buenas tardes"})


def test_rejects_a_multi_line_summary_and_over_long_text() -> None:
    with pytest.raises(ValidationError):
        handoff(request={"summary": "Cliente: hola\nAgente: hola", "intent": "dispute_new"})
    with pytest.raises(ValidationError):
        handoff(request={"summary": "x" * 501, "intent": "dispute_new"})
    with pytest.raises(ValidationError):
        handoff(open_questions=["q"] * 11)


def test_rejects_an_sla_before_creation_and_english_handoffs() -> None:
    with pytest.raises(ValidationError):
        handoff(sla_due=T0.replace(year=2025))
    with pytest.raises(ValidationError):
        handoff(language=Language.EN)


def test_round_trips_through_json_with_string_references() -> None:
    document = handoff()
    payload = document.model_dump(mode="json")
    assert payload["policy_basis"] == ["ESC-MX-1.2@1"]
    assert payload["verified_facts"][0]["source"] == "transactions:TXN-A-0001"
    assert Handoff.model_validate(payload) == document


def test_lifecycle_open_claimed_resolved() -> None:
    record = HandoffRecord(handoff=handoff())
    claimed = record.claim(AGENT, T0)
    assert claimed.status is HandoffStatus.CLAIMED
    resolved = claimed.resolve(AGENT, HandoffOutcomeCode.RESOLVED_BY_AGENT, "Case confirmed.", T0)
    assert resolved.status is HandoffStatus.RESOLVED
    assert resolved.handoff_id == "ho-000001"


def test_rejects_illegal_lifecycle_moves() -> None:
    record = HandoffRecord(handoff=handoff())
    with pytest.raises(InvalidHandoffTransitionError):
        record.resolve(AGENT, HandoffOutcomeCode.OTHER, "", T0)
    claimed = record.claim(AGENT, T0)
    with pytest.raises(InvalidHandoffTransitionError):
        claimed.claim(AGENT, T0)
    with pytest.raises(InvalidHandoffTransitionError):
        claimed.resolve(StaffId("agent-2"), HandoffOutcomeCode.OTHER, "", T0)
    with pytest.raises(ValidationError):
        HandoffRecord(handoff=handoff(), status=HandoffStatus.CLAIMED)
