"""Grounding verifier: action claims, catalog figures, eligibility outcomes, approval wording, internal figures."""

from decimal import Decimal

import pytest

from bank_agent.application.grounding.draft import FactKind, GroundingContext, RecordFact, ViolationKind
from bank_agent.application.grounding.verifier import GroundingVerifier
from bank_agent.domain.actions import ActionKind, ActionStatus
from bank_agent.domain.eligibility import EligibilityOutcome, ReviewReason
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.policy import PolicyClause
from bank_agent.domain.workflow import WorkflowId
from bank_agent_builders import elg_rule, eligibility_assessment, risk_estimate
from bank_agent_credit import catalog_products, credit_profiles
from bank_agent_grounding import NewerVersionRepository, context, draft, kinds, verified_action, verifier
from bank_agent_policy import fixture_pack

MX_LOAN = catalog_products()[1]  # MX-PL-FIXTURE: 10,000 to 300,000 MXN, 6 to 48 months, 20 % to 70 %
CO_CARD = catalog_products()[2]


@pytest.mark.parametrize(
    ("text", "language", "action"),
    [
        ("Bloqueamos tu tarjeta terminada en ****1234.", Language.ES, ActionKind.BLOCK_CARD),
        ("Tu tarjeta quedó bloqueada.", Language.ES, ActionKind.BLOCK_CARD),
        ("O seu cartão foi bloqueado.", Language.PT, ActionKind.BLOCK_CARD),
        ("We have blocked your card.", Language.EN, ActionKind.BLOCK_CARD),
        ("Registramos tu aclaración.", Language.ES, ActionKind.CREATE_DISPUTE_CASE),
        ("A sua contestação foi registrada.", Language.PT, ActionKind.CREATE_DISPUTE_CASE),
        ("Your dispute has been opened.", Language.EN, ActionKind.CREATE_DISPUTE_CASE),
        ("Registramos tu solicitud para revisión.", Language.ES, ActionKind.SUBMIT_CREDIT_APPLICATION),
        ("A sua solicitação foi registrada.", Language.PT, ActionKind.SUBMIT_CREDIT_APPLICATION),
    ],
)
def test_claiming_an_unverified_action_fails(text: str, language: Language, action: ActionKind) -> None:
    facts = (RecordFact(fact_id="card", kind=FactKind.REFERENCE, reference="1234"),)
    base = context(language=language, facts=facts)
    violations = verifier().verify(draft(text), base)
    assert kinds(violations) == [ViolationKind.UNVERIFIED_ACTION_CLAIM]
    assert violations[0].action is action
    verified = base.model_copy(update={"actions": (verified_action(action),)})
    assert verifier().verify(draft(text), verified) == ()


def test_an_executed_action_without_a_positive_read_back_is_not_verified() -> None:
    for action in (
        verified_action(ActionKind.BLOCK_CARD, verified=False),
        verified_action(ActionKind.BLOCK_CARD, status=ActionStatus.UNKNOWN, verified=False),
        verified_action(ActionKind.CREATE_DISPUTE_CASE),
    ):
        violations = verifier().verify(draft("Bloqueamos tu tarjeta."), context(actions=(action,)))
        assert kinds(violations) == [ViolationKind.UNVERIFIED_ACTION_CLAIM]


def test_offers_and_status_are_not_action_claims() -> None:
    text = "¿Quieres que bloqueemos tu tarjeta? Podemos registrar una aclaración. Tu tarjeta está bloqueada."
    assert verifier().verify(draft(text), context()) == ()


@pytest.mark.parametrize(
    "text", ["Desbloqueamos tu tarjeta.", "Reembolsamos el cargo.", "We have refunded the charge."]
)
def test_claims_of_actions_no_tool_performs_always_fail(text: str) -> None:
    actions = tuple(verified_action(kind) for kind in ActionKind)
    assert kinds(verifier().verify(draft(text), context(actions=actions))) == [ViolationKind.UNSUPPORTED_ACTION_CLAIM]


def credit(**overrides: object) -> GroundingContext:
    return context(**{"workflow": WorkflowId.CREDIT, "catalog_product": MX_LOAN, **overrides})


def test_catalog_figures_must_match_the_entry() -> None:
    good = "Montos de 10,000.00 MXN a 300,000.00 MXN, de 6 a 48 meses, con tasa anual de 20 % a 70 %."
    assert verifier().verify(draft(good), credit()) == ()
    rate = verifier().verify(draft("La tasa anual es de 45 %."), credit())
    assert kinds(rate) == [ViolationKind.RATE_NOT_IN_CATALOG]
    amount = verifier().verify(draft("Puedes pedir hasta 500,000.00 MXN."), credit())
    assert kinds(amount) == [ViolationKind.CATALOG_FIGURE_MISMATCH]
    term = verifier().verify(draft("El plazo llega a 60 meses."), credit())
    assert kinds(term) == [ViolationKind.CATALOG_FIGURE_MISMATCH]


def test_a_catalog_entry_from_another_jurisdiction_fails() -> None:
    violations = verifier().verify(draft("Te describimos el producto."), credit(catalog_product=CO_CARD))
    assert kinds(violations) == [ViolationKind.CATALOG_JURISDICTION_MISMATCH]


@pytest.mark.parametrize(
    ("text", "language"),
    [
        ("Tu crédito está preaprobado.", Language.ES),
        ("Tu solicitud fue aprobada.", Language.ES),
        ("Seu crédito foi pré-aprovado.", Language.PT),
        ("O empréstimo está aprovado.", Language.PT),
        ("Your loan is approved.", Language.EN),
        ("This is not an approval.", Language.EN),
    ],
)
def test_approval_wording_fails_in_credit_responses(text: str, language: Language) -> None:
    violations = verifier().verify(draft(text), credit(language=language))
    assert ViolationKind.APPROVAL_WORDING in kinds(violations)


def test_approval_wording_is_a_credit_check_only() -> None:
    assert verifier().verify(draft("Tu pago fue aprobado."), context(workflow=WorkflowId.ACCOUNT_INQUIRY)) == ()


ELIGIBLE_ES = "Según las reglas sintéticas, tu perfil cumple de forma indicativa las condiciones de este producto."
NOT_ELIGIBLE_ES = (
    "Según las reglas sintéticas, tu perfil no cumple por ahora las condiciones indicativas de este producto."
)
REVIEW = eligibility_assessment(
    outcome=EligibilityOutcome.REVIEW_REQUIRED, review_reasons=[ReviewReason.BORDERLINE_RISK_INTERVAL]
)
NOT_ELIGIBLE = eligibility_assessment(outcome=EligibilityOutcome.NOT_ELIGIBLE, rule_results=[elg_rule(passed=False)])


def test_an_eligibility_statement_needs_an_assessment() -> None:
    violations = verifier().verify(draft(ELIGIBLE_ES), credit())
    assert kinds(violations) == [ViolationKind.ELIGIBILITY_WITHOUT_ASSESSMENT]


@pytest.mark.parametrize(
    ("text", "language", "assessment"),
    [
        (ELIGIBLE_ES, Language.ES, REVIEW),
        ("O seu perfil atende de forma indicativa às condições deste produto.", Language.PT, NOT_ELIGIBLE),
        ("Your profile indicatively meets this product's conditions.", Language.EN, REVIEW),
        (NOT_ELIGIBLE_ES, Language.ES, eligibility_assessment()),
        ("Nos falta información para darte una orientación.", Language.ES, REVIEW),
    ],
)
def test_an_eligibility_outcome_that_differs_from_the_assessment_fails(
    text: str, language: Language, assessment: object
) -> None:
    violations = verifier().verify(draft(text), credit(language=language, eligibility=assessment))
    assert kinds(violations) == [ViolationKind.ELIGIBILITY_OUTCOME_MISMATCH]


def test_a_matching_eligibility_outcome_passes_and_negation_is_not_a_positive_claim() -> None:
    assert verifier().verify(draft(ELIGIBLE_ES), credit(eligibility=eligibility_assessment())) == ()
    assert verifier().verify(draft(NOT_ELIGIBLE_ES), credit(eligibility=NOT_ELIGIBLE)) == ()
    assert verifier().verify(draft("No eres elegible por ahora."), credit(eligibility=NOT_ELIGIBLE)) == ()
    review = "Tu caso necesita la revisión de una persona del equipo de crédito."
    assert verifier().verify(draft(review), credit(eligibility=REVIEW)) == ()


@pytest.mark.parametrize(
    "text",
    [
        "Tu puntaje de crédito es 712.",
        "Con un valor de 712 cumples.",
        "Tu probabilidad estimada de incumplimiento es 12 %.",
        "A estimativa é 0,12.",
        "Con tu ingreso de 32,000.00 MXN alcanza.",
        "Tu ingreso mensual declarado es 25,000.00 MXN.",
    ],
)
def test_risk_estimates_scores_and_income_never_appear(text: str) -> None:
    extra = credit(
        credit_profile=credit_profiles()[0],
        risk_estimate=risk_estimate(),
        declared_income=Money.of("25000.00", Currency.MXN),
        eligibility=eligibility_assessment(),
    )
    violations = verifier().verify(draft(text), extra)
    assert ViolationKind.INTERNAL_FIGURE_DISCLOSED in kinds(violations)


def test_a_clause_threshold_next_to_a_score_term_is_allowed() -> None:
    text = "Las reglas sintéticas piden un puntaje de crédito de al menos 650 y 12 meses como cliente."
    assert verifier().verify(draft(text, "ELG-MX-1.2@1"), credit(credit_profile=credit_profiles()[0])) == ()


def test_context_helpers() -> None:
    assert context(jurisdiction=Country.MX).is_credit is False
    assert context(eligibility=eligibility_assessment()).is_credit is True
    assert credit().catalog_product is not None
    assert Decimal(712) == Decimal(credit_profiles()[0].credit_score or 0)


class QuotingRepository(NewerVersionRepository):
    """The fixture pack with a realistic ``CRD-ALL-1`` body that describes a block in general terms."""

    BODY = "Solo te confirmaremos el bloqueo después de comprobar que la tarjeta quedó bloqueada. Nadie puede usarla."

    def get_clause(self, clause_id: str, language: Language, version: int | None = None) -> PolicyClause:
        clause = fixture_pack().get_clause(clause_id, language, version)
        return clause.model_copy(update={"body": self.BODY}) if clause_id == "CRD-ALL-1" else clause


def test_a_whole_quoted_policy_sentence_is_not_a_claim_but_a_fragment_of_it_is() -> None:
    engine = GroundingVerifier(QuotingRepository(fixture_pack()))
    quoted = "Solo te confirmaremos el bloqueo después de comprobar que la tarjeta quedó bloqueada."
    assert engine.verify(draft(quoted, "CRD-ALL-1@1"), context()) == ()
    fragment = engine.verify(draft("La tarjeta quedó bloqueada.", "CRD-ALL-1@1"), context())
    assert kinds(fragment) == [ViolationKind.UNVERIFIED_ACTION_CLAIM]
    uncited = engine.verify(draft(quoted), context())
    assert kinds(uncited) == [ViolationKind.UNVERIFIED_ACTION_CLAIM]
