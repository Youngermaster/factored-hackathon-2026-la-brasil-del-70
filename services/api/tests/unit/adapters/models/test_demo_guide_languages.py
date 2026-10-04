"""The web demo guide opens every conversation with a message the language detector places on its own.

A customer session takes the viewer's interface language, so a visitor whose browser is in English signs in with
``en``, which is not a customer language. A first message the detector cannot place then gets the language
question instead of the answer the guide describes (and a Portuguese interface would answer a Spanish message in
Portuguese). The local end-to-end run found three Spanish credit messages like that.
"""

import re
from pathlib import Path

import pytest

from bank_agent.adapters.models.lexical_language import LexicalLanguageDetector
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.locale import Language

ROOT = Path(__file__).resolve().parents[6]
SCENARIOS = ROOT / "apps" / "web" / "src" / "features" / "demo-guide" / "model" / "scenarios.ts"
_SCENARIO = re.compile(r"id: '(?P<id>[a-z-]+)'.*?\ses: \[(?P<es>.*?)\],\s*pt: \[(?P<pt>.*?)\],\s*\}", re.S)
_FIRST_MESSAGE = re.compile(r"say\(\s*'(?P<text>[^']+)'")


def _first_messages() -> list[tuple[str, Language, str]]:
    found = []
    for scenario in _SCENARIO.finditer(SCENARIOS.read_text(encoding="utf-8")):
        for language in (Language.ES, Language.PT):
            first = _FIRST_MESSAGE.search(scenario[language.value])
            if first is not None:
                found.append((scenario["id"], language, first["text"]))
    return found


def test_the_guide_has_a_first_message_per_scenario_and_language() -> None:
    messages = _first_messages()
    assert len(messages) >= 32
    assert {language for _, language, _ in messages} == {Language.ES, Language.PT}


@pytest.mark.parametrize(("scenario", "language", "text"), _first_messages())
def test_each_first_message_is_detected_in_its_language(scenario: str, language: Language, text: str) -> None:
    detection = LexicalLanguageDetector().detect(UntrustedText(text))
    assert detection.language is language, f"{scenario} ({language.value}): {text!r}"
