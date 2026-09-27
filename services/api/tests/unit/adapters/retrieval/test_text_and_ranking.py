"""Tokenization (accent folding, stopwords, truncation) and reciprocal rank fusion."""

import pytest

from bank_agent.adapters.retrieval.ranking import reciprocal_rank_fusion
from bank_agent.adapters.retrieval.text import PREFIX_LENGTH, STOPWORDS, fold, tokenize
from bank_agent.domain.decision import ClauseRef
from bank_agent.domain.locale import Language


@pytest.mark.parametrize(
    ("text", "folded"),
    [
        ("Días Hábiles", "dias habiles"),
        ("Cartão bloqueado ÚLTIMOS", "cartao bloqueado ultimos"),
        ("reclamación, aclaración", "reclamacion, aclaracion"),
        ("pré-aprovação", "pre-aprovacao"),
    ],
)
def test_fold_removes_accents_and_case(text: str, folded: str) -> None:
    assert fold(text) == folded


def test_spanish_and_portuguese_spellings_meet_on_the_same_tokens() -> None:
    assert tokenize("60 días", Language.ES) == tokenize("60 dias", Language.PT) == ("60", "dias")
    assert tokenize("tarjeta", Language.ES) == tokenize("tarjetas", Language.ES) == ("tarjet",)


def test_truncation_joins_inflections_of_one_stem() -> None:
    stems = {tokenize(word, Language.ES)[0] for word in ("bloquear", "bloqueo", "bloqueada", "bloqueamos")}
    assert stems == {"bloque"}
    assert all(len(token) <= PREFIX_LENGTH for token in tokenize("reclamaciones disputadas", Language.ES))


def test_stopwords_depend_on_the_language() -> None:
    assert tokenize("¿Cuál es el plazo para mi tarjeta?", Language.ES) == ("plazo", "tarjet")
    assert tokenize("Qual é o prazo do meu cartão?", Language.PT) == ("prazo", "cartao")
    assert tokenize("What is the window for my card?", Language.EN) == ("window", "card")
    assert "que" in STOPWORDS[Language.ES]
    assert "nao" in STOPWORDS[Language.PT]


def test_numbers_stay_whole_and_single_letters_drop() -> None:
    assert tokenize("2000000 COP y 90 días", Language.ES) == ("2000000", "cop", "90", "dias")
    assert tokenize("x 7", Language.ES) == ("7",)


def ref(clause_id: str) -> ClauseRef:
    return ClauseRef(clause_id=clause_id, version=1)


def test_fusion_sums_reciprocal_ranks() -> None:
    first = [ref("DSP-MX-1"), ref("DSP-MX-2"), ref("CRD-ALL-1")]
    second = [ref("DSP-MX-2"), ref("ACC-ALL-1")]
    fused = dict(reciprocal_rank_fusion([first, second], k=60))
    assert fused[ref("DSP-MX-2")] == pytest.approx(1 / 62 + 1 / 61)
    assert fused[ref("DSP-MX-1")] == pytest.approx(1 / 61)
    assert fused[ref("ACC-ALL-1")] == pytest.approx(1 / 62)
    assert fused[ref("CRD-ALL-1")] == pytest.approx(1 / 63)
    assert [item for item, _ in reciprocal_rank_fusion([first, second], k=60)][:2] == [ref("DSP-MX-2"), ref("DSP-MX-1")]


def test_fusion_breaks_ties_by_clause_id_and_accepts_k_zero() -> None:
    fused = reciprocal_rank_fusion([[ref("DSP-MX-1")], [ref("ACC-ALL-1")]], k=0)
    assert fused == [(ref("ACC-ALL-1"), 1.0), (ref("DSP-MX-1"), 1.0)]
    assert reciprocal_rank_fusion([], k=60) == []


def test_fusion_refuses_a_negative_constant() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        reciprocal_rank_fusion([[ref("DSP-MX-1")]], k=-1)
