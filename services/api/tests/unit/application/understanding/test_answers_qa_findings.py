"""Option-choice regressions from the production QA pass of 2026-10-05 (CRE-01)."""

import pytest

from bank_agent.application.understanding.answers import parse_choice


@pytest.mark.parametrize("text", ["uno personal", "quiero una hipoteca", "dos cosas: saldo y tarjeta"])
def test_cre01_a_number_word_used_as_an_article_is_not_a_choice(text: str) -> None:
    assert parse_choice(text, ["a", "b", "c"]) is None


@pytest.mark.parametrize(("text", "index"), [("uno", 0), ("la una", 0), ("dos", 1), ("o dois", 1), ("tres", 2)])
def test_cre01_a_bare_number_word_is_still_a_choice(text: str, index: int) -> None:
    assert parse_choice(text, ["a", "b", "c"]) == index
