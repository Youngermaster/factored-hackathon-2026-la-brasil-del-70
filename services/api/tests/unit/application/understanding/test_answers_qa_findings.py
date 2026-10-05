"""Answer-parsing regressions from the production QA pass of 2026-10-05 (CRE-01, R2)."""

import pytest

from bank_agent.application.understanding.answers import YesNo, parse_choice, parse_yes_no


@pytest.mark.parametrize("text", ["uno personal", "quiero una hipoteca", "dos cosas: saldo y tarjeta"])
def test_cre01_a_number_word_used_as_an_article_is_not_a_choice(text: str) -> None:
    assert parse_choice(text, ["a", "b", "c"]) is None


@pytest.mark.parametrize(("text", "index"), [("uno", 0), ("la una", 0), ("dos", 1), ("o dois", 1), ("tres", 2)])
def test_cre01_a_bare_number_word_is_still_a_choice(text: str, index: int) -> None:
    assert parse_choice(text, ["a", "b", "c"]) == index


@pytest.mark.parametrize(
    "text",
    ["no, mejor no la bloquees", "cancela el bloqueo", "olvídalo", "não, não bloqueie", "desisto", "esquece"],
)
def test_a_refusal_sent_after_a_step_up_reads_as_no(text: str) -> None:
    """Production QA R2: the refusal that withdraws consent after a step-up must parse as no in es and pt."""
    assert parse_yes_no(text) is YesNo.NO
