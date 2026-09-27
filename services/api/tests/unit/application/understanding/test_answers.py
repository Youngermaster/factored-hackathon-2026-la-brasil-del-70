"""Yes and no parsing for Spanish and Portuguese, option choices, and the language choice."""

import pytest

from bank_agent.application.understanding.answers import YesNo, parse_choice, parse_language_choice, parse_yes_no
from bank_agent.domain.locale import Language


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("sí", YesNo.YES),
        ("Sí, dale", YesNo.YES),
        ("de una", YesNo.YES),
        ("claro, confirmo", YesNo.YES),
        ("sim, pode", YesNo.YES),
        ("beleza", YesNo.YES),
        ("com certeza", YesNo.YES),
        ("no", YesNo.NO),
        ("nel", YesNo.NO),
        ("mejor no", YesNo.NO),
        ("não", YesNo.NO),
        ("ainda não", YesNo.NO),
        ("sí pero no", YesNo.UNCLEAR),
        ("claro que no", YesNo.UNCLEAR),
        ("no sé", YesNo.UNCLEAR),
        ("não sei", YesNo.UNCLEAR),
        ("quizás", YesNo.UNCLEAR),
        ("el cargo es de otra tienda que conozco muy bien desde hace años", YesNo.UNCLEAR),
        ("", YesNo.UNCLEAR),
    ],
)
def test_parses_yes_and_no(text: str, expected: YesNo) -> None:
    assert parse_yes_no(text) is expected


@pytest.mark.parametrize(
    ("text", "index"),
    [("1", 0), ("la segunda", 1), ("a primeira", 0), ("opción 3", 2), ("la tercera", 2), ("la del medio", None)],
)
def test_parses_ordinal_choices(text: str, index: int | None) -> None:
    assert parse_choice(text, ["a", "b", "c"]) == index


def test_an_attribute_must_match_exactly_one_option() -> None:
    options = ["cafe luna", "super norte", "cafe sol"]

    def matches(folded: str, option: str) -> bool:
        return any(word in folded.split() for word in option.split())

    assert parse_choice("la de super", options, matches) == 1
    assert parse_choice("la del cafe", options, matches) is None
    assert parse_choice("1 o 2", options, matches) is None


@pytest.mark.parametrize(
    ("text", "language"),
    [("español", Language.ES), ("Português, por favor", Language.PT), ("1", Language.ES), ("2", Language.PT)],
)
def test_parses_the_language_choice(text: str, language: Language) -> None:
    assert parse_language_choice(text) is language


def test_both_or_neither_language_is_no_choice() -> None:
    assert parse_language_choice("español o portugués") is None
    assert parse_language_choice("tanto faz") is None
