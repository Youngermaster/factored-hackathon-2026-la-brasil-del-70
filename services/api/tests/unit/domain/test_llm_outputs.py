from decimal import Decimal

import pytest
from pydantic import ValidationError

from bank_agent.domain.base import internal_fields, pii_fields
from bank_agent.domain.errors import LlmProviderError, LlmProviderRejectedError
from bank_agent.domain.intelligence import LlmCallContext, PromptRef, PromptValue, canonical_variables, input_hash
from bank_agent.domain.llm_outputs import (
    OUTPUT_MODELS,
    CardHint,
    CreditSlotExtraction,
    DisputeSlotExtraction,
    EscalationSignals,
    ExtractedTransaction,
    FallbackIntentLabel,
    HandoffSummaryDraft,
    IntentClassification,
    forbidden_variable_reason,
)
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.product import ProductType
from bank_agent.domain.workflow import Intent
from bank_agent.testing import fake_llm


def test_fallback_labels_are_every_intent_plus_out_of_scope() -> None:
    assert {label.value for label in FallbackIntentLabel} == {intent.value for intent in Intent} | {"out_of_scope"}
    assert FallbackIntentLabel.OUT_OF_SCOPE.intent is None
    assert FallbackIntentLabel.CARD_BLOCK.intent is Intent.CARD_BLOCK


def test_extraction_fields_must_be_stated_explicitly() -> None:
    with pytest.raises(ValidationError, match="transaction"):
        DisputeSlotExtraction.model_validate({"intent_candidates": [], "reason_candidates": []})

    result = DisputeSlotExtraction.model_validate(
        {"intent_candidates": [], "transaction": None, "reason_candidates": []}
    )

    assert result.transaction is None


def test_extracted_transaction_becomes_a_descriptor_without_date_interpretations() -> None:
    extracted = ExtractedTransaction.model_validate(
        {
            "amount": "120.50",
            "currency_hint": "MXN",
            "merchant_text": "Oxxo",
            "date_expression": "ayer",
            "channel_hint": None,
            "card_last4_hint": "4821",
        }
    )

    descriptor = extracted.to_descriptor()

    assert descriptor.amount == Decimal("120.50")
    assert descriptor.merchant_text == "Oxxo"
    assert descriptor.date_interpretations == ()


def test_card_hint_accepts_only_card_products() -> None:
    assert CardHint(card_type=ProductType.DEBIT_CARD, last4=None).card_type is ProductType.DEBIT_CARD
    with pytest.raises(ValidationError, match="credit or debit card"):
        CardHint(card_type=ProductType.MORTGAGE, last4=None)


def test_declared_income_is_marked_personal_data_and_nothing_is_internal() -> None:
    assert pii_fields(CreditSlotExtraction) == {"declared_monthly_income": "financial"}
    for model in OUTPUT_MODELS.values():
        assert internal_fields(model) == frozenset()


def test_intent_classification_rejects_repeated_labels() -> None:
    with pytest.raises(ValidationError, match="only once"):
        IntentClassification.model_validate(
            {"candidates": [{"label": "card_block", "confidence": 0.6}, {"label": "card_block", "confidence": 0.3}]}
        )


def test_escalation_signals_report_any() -> None:
    quiet = EscalationSignals(
        legal_or_regulator_mention=False, distress=False, human_requested=False, third_party_admission=False
    )
    assert not quiet.any
    assert quiet.evolve(distress=True).any


def test_handoff_summary_is_one_paragraph_with_cited_facts() -> None:
    with pytest.raises(ValidationError):
        HandoffSummaryDraft(summary="line one\nline two", cited_fact_ids=("F1",))
    with pytest.raises(ValidationError):
        HandoffSummaryDraft(summary="Customer reports a lost card.", cited_fact_ids=())


@pytest.mark.parametrize(
    "name",
    [
        "credit_score",
        "estimated_monthly_income",
        "max_days_past_due",
        "utilization",
        "probability",
        "interval_low",
        "fraud",
        "risk_band",
        "customer_income",
        "internal_flags",
        "monthly_income_usd",
        "requested_amount_to_income",
        "days_past_due_count",
    ],
)
def test_forbids_variables_that_carry_internal_data(name: str) -> None:
    assert forbidden_variable_reason(name) is not None


@pytest.mark.parametrize(
    "name", ["customer_message", "eligibility_outcome", "eligibility_reasons", "disclaimer", "facts", "dialect_hint"]
)
def test_allows_ordinary_variables(name: str) -> None:
    assert forbidden_variable_reason(name) is None


def test_canonicalization_lives_in_the_domain_and_the_fake_reexports_it() -> None:
    variables: dict[str, PromptValue] = {
        "b": Money(amount=Decimal("1.50"), currency=Currency.MXN),
        "a": ["x", "y"],
        "c": None,
    }
    prompt = PromptRef.model_validate("phrase_response@1")

    assert canonical_variables(variables) == '{"a":["x","y"],"b":{"amount":"1.50","currency":"MXN"},"c":null}'
    assert fake_llm.input_hash is input_hash
    assert len(input_hash(prompt, variables)) == 64


def test_call_context_sensitive_terms_are_personal_data() -> None:
    context = LlmCallContext(sensitive_terms=("Mariana",))

    assert pii_fields(LlmCallContext) == {"sensitive_terms": "name"}
    assert context.sensitive_terms == ("Mariana",)


def test_provider_rejection_is_a_provider_error_that_is_never_retried() -> None:
    assert issubclass(LlmProviderRejectedError, LlmProviderError)
    assert LlmProviderError.retryable
    assert not LlmProviderRejectedError.retryable
