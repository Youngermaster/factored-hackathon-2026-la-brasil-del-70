"""``policy_excerpts`` renders a handoff's policy basis from the pack, in the handoff's language, skipping unknowns."""

from bank_agent.api.schemas.agent import HandoffView, policy_excerpts
from bank_agent.application.engine.render import MAX_EXCERPT
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.errors import PolicyClauseNotFoundError
from bank_agent.domain.handoff import HandoffRecord
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.policy import PolicyClause
from bank_agent_builders import handoff_v1_1
from bank_agent_policy import clause

LIMIT = {"auto_intake_max_amount": Money.of("10000.00", Currency.MXN)}
ESC = ClauseRef.parse("ESC-ALL-1@1")
DSP = ClauseRef.parse("DSP-MX-3@2")
UNKNOWN = ClauseRef.parse("ESC-ALL-9@1")


class FixtureClauses:
    """Clauses by id, language, and version, raising like the pack for anything else. Test double."""

    def __init__(self, *clauses: PolicyClause) -> None:
        self._clauses = {(c.metadata.clause_id, c.metadata.language, c.metadata.version): c for c in clauses}

    def get_clause(self, clause_id: str, language: Language, version: int | None = None) -> PolicyClause:
        found = self._clauses.get((clause_id, language, version or 1))
        if found is None:
            raise PolicyClauseNotFoundError(f"unknown clause {clause_id}")
        return found


CLAUSES = FixtureClauses(
    clause("ESC-ALL-1", body="Una persona revisa el caso.", language=Language.ES),
    clause("ESC-ALL-1", body="Uma pessoa revisa o caso.", language=Language.PT),
    clause("DSP-MX-3", params=LIMIT, body="Hasta {auto_intake_max_amount}.", language=Language.ES, version=2),
    clause("DSP-MX-3", params=LIMIT, body="Até {auto_intake_max_amount}.", language=Language.PT, version=2),
)


def test_excerpts_follow_the_basis_order_in_the_requested_language_and_locale() -> None:
    portuguese = policy_excerpts(CLAUSES, (DSP, ESC), Language.PT, Country.MX)
    spanish = policy_excerpts(CLAUSES, (DSP, ESC), Language.ES, Country.CO)
    assert [(c.clause, c.excerpt) for c in portuguese] == [
        (DSP, "Até 10.000,00 MXN."),
        (ESC, "Uma pessoa revisa o caso."),
    ]
    assert [c.excerpt for c in spanish] == ["Hasta 10.000,00 MXN.", "Una persona revisa el caso."]
    assert policy_excerpts(CLAUSES, (DSP,), Language.ES, Country.MX)[0].excerpt == "Hasta 10,000.00 MXN."


def test_a_clause_the_pack_cannot_resolve_is_left_out() -> None:
    wrong_version = ClauseRef.parse("ESC-ALL-1@2")
    excerpts = policy_excerpts(CLAUSES, (UNKNOWN, ESC, wrong_version), Language.PT, Country.MX)
    assert [c.clause for c in excerpts] == [ESC]
    assert policy_excerpts(CLAUSES, (ESC,), Language.EN, Country.MX) == ()


def test_a_long_clause_is_cut_to_the_citation_limit() -> None:
    long_clause = FixtureClauses(clause("ESC-ALL-1", body="x" * (MAX_EXCERPT + 50), language=Language.ES))
    (excerpt,) = policy_excerpts(long_clause, (ESC,), Language.ES, Country.MX)
    assert len(excerpt.excerpt) == MAX_EXCERPT


def test_the_handoff_view_carries_the_excerpts_of_its_policy_basis() -> None:
    document = handoff_v1_1(language=Language.PT, policy_basis=[ESC, UNKNOWN, DSP])
    view = HandoffView.of(HandoffRecord(handoff=document), CLAUSES)
    assert view.policy_basis == (ESC, UNKNOWN, DSP)
    assert [(c.clause, c.excerpt) for c in view.policy_excerpts] == [
        (ESC, "Uma pessoa revisa o caso."),
        (DSP, "Até 10.000,00 MXN."),
    ]
