"""Grounding verifier: citations, figures against clause parameters and record facts, currencies, balances."""

from datetime import date

import pytest

from bank_agent.application.grounding.draft import FactKind, RecordFact, ViolationKind
from bank_agent.application.grounding.verifier import GroundingVerifier
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.money import Currency
from bank_agent_grounding import (
    NewerVersionRepository,
    as_of,
    context,
    date_fact,
    draft,
    kinds,
    money_fact,
    number_fact,
    refs,
    verifier,
)
from bank_agent_policy import fixture_pack

WINDOW = "Tienes 90 días naturales para aclarar un cargo [DSP-MX-1]. El límite automático es de 10,000.00 MXN."


def test_a_correct_draft_passes() -> None:
    assert verifier().verify(draft(WINDOW, "DSP-MX-3@1"), context()) == ()


def test_a_citation_to_a_nonexistent_clause_fails() -> None:
    violations = verifier().verify(draft("Consulta la política.", "DSP-MX-9@1"), context())
    assert kinds(violations) == [ViolationKind.UNKNOWN_CLAUSE]
    assert violations[0].clause_id == "DSP-MX-9"


def test_a_stale_clause_version_fails_and_its_parameters_do_not_count() -> None:
    engine = GroundingVerifier(NewerVersionRepository(fixture_pack()))
    violations = engine.verify(draft("Tienes 90 días.", "DSP-MX-1@1"), context())
    assert kinds(violations) == [ViolationKind.STALE_CLAUSE_VERSION, ViolationKind.UNSUPPORTED_DURATION]
    inline = engine.verify(draft("Tienes 90 días [DSP-MX-1@1]."), context())
    assert ViolationKind.STALE_CLAUSE_VERSION in kinds(inline)
    assert engine.verify(draft("Tienes 90 días.", "DSP-MX-1@2"), context()) == ()


def test_a_clause_of_another_jurisdiction_fails() -> None:
    violations = verifier().verify(draft("Tienes 90 días.", "DSP-MX-1@1"), context(jurisdiction=Country.CO))
    assert kinds(violations)[0] is ViolationKind.CLAUSE_OUTSIDE_JURISDICTION


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("Tienes 60 días naturales para aclarar un cargo.", ViolationKind.UNSUPPORTED_DURATION),
        ("Tienes 90 horas para aclarar un cargo.", ViolationKind.UNSUPPORTED_DURATION),
        ("El límite automático es de 10,500.00 MXN.", ViolationKind.UNSUPPORTED_AMOUNT),
        ("Revisamos 3 reclamaciones.", ViolationKind.UNSUPPORTED_NUMBER),
        ("La tasa es de 12 %.", ViolationKind.UNSUPPORTED_NUMBER),
        ("Tu caso vence el 20 de junio de 2026.", ViolationKind.UNSUPPORTED_DATE),
        ("Tu tarjeta ****9999 está activa.", ViolationKind.UNSUPPORTED_REFERENCE),
    ],
)
def test_drift_in_a_figure_fails(text: str, kind: ViolationKind) -> None:
    violations = verifier().verify(draft(text, "DSP-MX-1@1", "DSP-MX-3@1"), context())
    assert kinds(violations) == [kind]
    assert violations[0].span is not None


def test_bound_clause_parameters_count_without_a_citation() -> None:
    text = "Tienes 90 días naturales."
    assert kinds(verifier().verify(draft(text), context())) == [ViolationKind.UNSUPPORTED_DURATION]
    assert verifier().verify(draft(text), context(bound_clauses=refs("DSP-MX-1@1"))) == ()


def test_record_facts_support_counts_dates_days_and_references() -> None:
    facts = (
        number_fact(FactKind.COUNT, 3),
        number_fact(FactKind.DAYS, 12),
        date_fact(date(2026, 6, 20)),
        RecordFact(fact_id="card", kind=FactKind.REFERENCE, reference="9999"),
    )
    text = "Tienes 3 tarjetas; la ****9999 venció hace 12 días, el 20 de junio de 2026 (20 de junio)."
    assert verifier().verify(draft(text), context(facts=facts)) == ()


def test_pt_formats_match_the_same_facts() -> None:
    facts = (money_fact(FactKind.BALANCE, "1250.00"), as_of())
    text = "O saldo do seu cartão é $ 1.250,00 em 17 de junho de 2026, às 10:30."
    assert verifier().verify(draft(text), context(language=Language.PT, facts=facts)) == ()


def test_currency_symbols_resolve_from_the_account_currency() -> None:
    facts = (money_fact(FactKind.BALANCE, "1250.00"), as_of())
    good = "Tu saldo es de $1,250.00 al 17 de junio de 2026."
    assert verifier().verify(draft(good), context(facts=facts)) == ()
    conflict = "Tu saldo es de USD 1,250.00 al 17 de junio de 2026."
    assert kinds(verifier().verify(draft(conflict), context(facts=facts))) == [ViolationKind.CURRENCY_CONFLICT]
    brazil = "O saldo é R$ 1.250,00 em 17 de junho de 2026."
    pt = context(language=Language.PT, facts=facts)
    assert kinds(verifier().verify(draft(brazil), pt)) == [ViolationKind.CURRENCY_CONFLICT]
    unresolved = verifier().verify(draft(good), context(facts=facts, currency=None))
    assert kinds(unresolved) == [ViolationKind.CURRENCY_UNRESOLVED]


def test_an_explicit_code_matching_a_clause_parameter_passes_for_another_account_currency() -> None:
    text = "El límite automático es de 10,000.00 MXN."
    assert verifier().verify(draft(text, "DSP-MX-3@1"), context(currency=Currency.USD)) == ()
    assert kinds(verifier().verify(draft("Son 500 pesos.", "DSP-MX-3@1"), context(currency=Currency.USD))) == [
        ViolationKind.CURRENCY_CONFLICT
    ]


def test_a_balance_without_its_as_of_date_fails() -> None:
    facts = (money_fact(FactKind.BALANCE, "1250.00"), as_of())
    violations = verifier().verify(draft("Tu saldo es de $1,250.00."), context(facts=facts))
    assert kinds(violations) == [ViolationKind.BALANCE_WITHOUT_AS_OF]
    other_day = verifier().verify(draft("Tu saldo es de $1,250.00 al 16 de junio de 2026."), context(facts=facts))
    assert ViolationKind.BALANCE_WITHOUT_AS_OF in kinds(other_day)


def test_balances_and_totals_must_match_their_own_facts() -> None:
    facts = (
        money_fact(FactKind.BALANCE, "1250.00"),
        money_fact(FactKind.STATEMENT_TOTAL, "800.00", fact_id="t"),
        as_of(),
    )
    wrong_balance = "Tu saldo es de $800.00 al 17 de junio de 2026."
    assert kinds(verifier().verify(draft(wrong_balance), context(facts=facts))) == [ViolationKind.BALANCE_MISMATCH]
    wrong_total = "El total de cargos del periodo es $1,250.00."
    assert kinds(verifier().verify(draft(wrong_total), context(facts=facts))) == [
        ViolationKind.STATEMENT_TOTAL_MISMATCH
    ]
    right = "El total de cargos del periodo es $800.00. Tu saldo es 1,250.00 al 17 de junio de 2026."
    assert verifier().verify(draft(right), context(facts=facts)) == ()
    bare = "Tu saldo es 1,300.00 al 17 de junio de 2026."
    assert kinds(verifier().verify(draft(bare), context(facts=facts))) == [ViolationKind.BALANCE_MISMATCH]
