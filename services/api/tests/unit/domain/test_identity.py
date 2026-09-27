import pytest
from pydantic import TypeAdapter, ValidationError

from bank_agent.domain.access import AuthLevel, Role
from bank_agent.domain.identifiers import ChallengeId, CustomerId, StaffId
from bank_agent.domain.identity import (
    DocumentIdentification,
    Identification,
    OtpDeliveryReceipt,
    OtpDispatch,
    OtpPurpose,
    PersonaIdentification,
    VerifiedIdentity,
)
from bank_agent_builders import T0

CHALLENGE = ChallengeId("chl-1")
CUSTOMER = CustomerId("C1")
IDENTIFICATION: TypeAdapter[PersonaIdentification | DocumentIdentification] = TypeAdapter(Identification)


def test_parses_both_identification_kinds() -> None:
    assert isinstance(
        IDENTIFICATION.validate_python({"kind": "persona", "persona_id": "persona-mx-1"}), PersonaIdentification
    )
    document = IDENTIFICATION.validate_python(
        {"kind": "document", "document_number": "CURP1234", "phone_last4": "5678"}
    )
    assert isinstance(document, DocumentIdentification)


def test_document_data_and_codes_stay_out_of_repr() -> None:
    document = DocumentIdentification(document_number="CURP1234", phone_last4="5678")
    assert "CURP1234" not in repr(document)
    assert "5678" not in repr(document)
    receipt = OtpDeliveryReceipt(delivered=True, channel="demo", demo_code="123456")
    assert "123456" not in repr(receipt)


def test_dispatch_has_exactly_one_recipient() -> None:
    with pytest.raises(ValidationError):
        OtpDispatch(challenge_id=CHALLENGE, purpose=OtpPurpose.LOGIN, code="123456", expires_at=T0)
    with pytest.raises(ValidationError):
        OtpDispatch(
            challenge_id=CHALLENGE,
            purpose=OtpPurpose.LOGIN,
            recipient_customer_id=CUSTOMER,
            recipient_staff_id=StaffId("agent-1"),
            code="123456",
            expires_at=T0,
        )


def test_rejects_malformed_codes() -> None:
    with pytest.raises(ValidationError):
        OtpDispatch(
            challenge_id=CHALLENGE,
            purpose=OtpPurpose.LOGIN,
            recipient_customer_id=CUSTOMER,
            code="12345",
            expires_at=T0,
        )


def test_verified_identity_is_exactly_otp_verified() -> None:
    verified_level = AuthLevel.OTP_VERIFIED
    identity = VerifiedIdentity(role=Role.CUSTOMER, customer_id=CUSTOMER, auth_level=verified_level, verified_at=T0)
    assert identity.customer_id == "C1"
    for level in (AuthLevel.IDENTIFIED, AuthLevel.STEP_UP):
        with pytest.raises(ValidationError):
            VerifiedIdentity(role=Role.CUSTOMER, customer_id=CUSTOMER, auth_level=level, verified_at=T0)
