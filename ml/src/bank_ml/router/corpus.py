"""The router corpus: team-authored seed utterances and the augmentation lexicon under ``ml/corpus/router``.

Organizer transcripts carry no intent signal (``docs/analysis/labeling-protocol.md``), so every router utterance
starts as a team-authored seed. A seed file holds one intent with eight seeds per locale; the loader checks the
intent, the locales, the slot names, and that every intent has seeds in every locale.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from bank_agent.domain.workflow import Intent
from bank_ml.common.reports import REPOSITORY_ROOT

CORPUS_DIR = REPOSITORY_ROOT / "ml" / "corpus" / "router"
LOCALES = ("es-MX", "es-CO", "es-AR", "pt-BR")
SLOTS = frozenset({"amount", "merchant", "date", "last4", "product"})
SCOPES = frozenset({"banking_unsupported", "off_domain"})
SLOT_PATTERN = re.compile(r"\{(\w+)\}")


class CorpusError(ValueError):
    """The seed corpus or the lexicon is malformed."""


@dataclass(frozen=True)
class Seed:
    seed_id: str
    intent: Intent
    locale: str
    template: str
    scope: str | None = None

    @property
    def language(self) -> str:
        return self.locale.split("-")[0]

    @property
    def slots(self) -> tuple[str, ...]:
        return tuple(SLOT_PATTERN.findall(self.template))


@dataclass(frozen=True)
class Lexicon:
    slots: Mapping[str, Mapping[str, Sequence[str]]]
    slang: Mapping[str, Mapping[str, Sequence[str]]]
    fillers: Mapping[str, Sequence[str]]
    homophones: Mapping[str, Mapping[str, str]]
    keyboard: Mapping[str, str]


def _entry(intent: Intent, locale: str, raw: Any) -> tuple[str, str | None]:
    if isinstance(raw, str):
        text, scope = raw, None
    elif isinstance(raw, dict) and isinstance(raw.get("text"), str):
        text, scope = raw["text"], raw.get("scope")
    else:
        raise CorpusError(f"{intent}/{locale}: a seed is a string or a mapping with text")
    if (intent is Intent.UNSUPPORTED) != (scope is not None) or (scope is not None and scope not in SCOPES):
        raise CorpusError(f"{intent}/{locale}: unsupported seeds need a scope, other seeds none: {text!r}")
    unknown = set(SLOT_PATTERN.findall(text)) - SLOTS
    if unknown:
        raise CorpusError(f"{intent}/{locale}: unknown slots {sorted(unknown)} in {text!r}")
    return text.strip(), scope


def load_seeds(corpus_dir: Path = CORPUS_DIR) -> list[Seed]:
    seeds: list[Seed] = []
    files = sorted((corpus_dir / "seeds").glob("*.yaml"))
    for path in files:
        document = yaml.safe_load(path.read_text(encoding="utf-8"))
        try:
            intent = Intent(document["intent"])
        except (KeyError, TypeError, ValueError):
            raise CorpusError(f"{path.name}: missing or unknown intent") from None
        if path.stem != intent.value:
            raise CorpusError(f"{path.name}: the file name must be the intent")
        by_locale = document.get("seeds") or {}
        if set(by_locale) != set(LOCALES):
            raise CorpusError(f"{path.name}: seeds need exactly the locales {', '.join(LOCALES)}")
        for locale in LOCALES:
            for number, raw in enumerate(by_locale[locale], start=1):
                text, scope = _entry(intent, locale, raw)
                seeds.append(Seed(f"{intent.value}:{locale}:{number:02d}", intent, locale, text, scope))
    missing = set(Intent) - {seed.intent for seed in seeds}
    if missing:
        raise CorpusError(f"no seeds for intents: {sorted(intent.value for intent in missing)}")
    return seeds


def load_lexicon(corpus_dir: Path = CORPUS_DIR) -> Lexicon:
    document = yaml.safe_load((corpus_dir / "lexicon.yaml").read_text(encoding="utf-8"))
    lexicon = Lexicon(
        slots=document["slots"],
        slang=document["slang"],
        fillers=document["fillers"],
        homophones=document["homophones"],
        keyboard=document["keyboard"],
    )
    for slot in SLOTS:
        for locale in LOCALES:
            if not lexicon.slots.get(slot, {}).get(locale):
                raise CorpusError(f"lexicon: slot {slot} has no values for {locale}")
    return lexicon
