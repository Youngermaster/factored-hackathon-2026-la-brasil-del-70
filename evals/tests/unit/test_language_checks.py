import json
from pathlib import Path
from typing import Any

import pytest

from bank_evals.language_checks import portuguese_problems, spanish_problems

CASSETTES = Path(__file__).resolve().parents[2] / "cassettes"
APPROVAL_WORDS = ("aprobad", "aprovad", "approved", "garantizad", "garantid")


def _phrase_cassettes() -> list[dict[str, Any]]:
    fixtures = sorted(path for path in CASSETTES.rglob("*.json") if not path.is_relative_to(CASSETTES / "eval"))
    documents = [json.loads(path.read_text(encoding="utf-8")) for path in fixtures]
    return [document for document in documents if document["prompt"] == "phrase_response@1"]


@pytest.mark.parametrize(
    "text",
    [
        "O saldo disponível da sua conta poupança é de 1200.00 MXN.",
        "Pronto: seu cartão foi bloqueado.",
        "Abrimos a contestação e o prazo de resposta é de 10 dias úteis.",
    ],
)
def test_accepts_natural_brazilian_portuguese(text: str) -> None:
    assert portuguese_problems(text) == []


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("Su tarjeta fue bloqueada y el caso quedó abierto.", "Spanish word or phrase: su"),
        ("¿Você quer bloquear o cartão?", "Spanish punctuation or letter"),
        ("Gracias, seu cartão foi bloqueado.", "Spanish word or phrase: gracias"),
        ("OK 1234.", "no Portuguese marker"),
    ],
)
def test_flags_spanish_in_a_portuguese_reply(text: str, problem: str) -> None:
    assert problem in portuguese_problems(text)


@pytest.mark.parametrize(
    ("text", "problem"),
    [
        ("Su tarjeta foi bloqueada, você pode esperar.", "Portuguese word: você"),
        ("La contestação fue abierta.", "Portuguese orthography"),
        ("OK 1234.", "no Spanish marker"),
    ],
)
def test_flags_portuguese_in_a_spanish_reply(text: str, problem: str) -> None:
    assert problem in spanish_problems(text)


def test_every_workflow_has_a_phrase_cassette_in_both_languages() -> None:
    seen = {(document["labels"]["workflow"], document["language"]) for document in _phrase_cassettes()}

    assert seen == {
        (workflow, language)
        for workflow in ("account_inquiry", "card_support", "dispute", "credit")
        for language in ("es", "pt")
    }


@pytest.mark.parametrize("document", _phrase_cassettes(), ids=lambda d: f"{d['labels']['workflow']}-{d['language']}")
def test_phrase_cassettes_are_in_the_session_language_and_never_imply_approval(document: dict[str, Any]) -> None:
    text = document["output"]
    assert isinstance(text, str)

    problems = portuguese_problems(text) if document["language"] == "pt" else spanish_problems(text)

    assert problems == []
    assert not any(word in text.lower() for word in APPROVAL_WORDS)
    variables = document["variables"]
    assert isinstance(variables, dict)
    if "disclaimer" in variables:
        assert text.endswith(variables["disclaimer"])
