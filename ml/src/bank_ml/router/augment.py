"""Deterministic augmentation of one seed into labeled items, each with its provenance.

For a seed, in order (randomness from ``rng("augment", seed_id)``):

1. ``canonical``: slots filled with the first lexicon value (provenance ``team_authored``: the words are the team's).
2. ``slots``: up to three fills drawn from the locale's slot lists (only for seeds with slots).
3. ``slang``: the locale's slang table applied to the canonical text (only when a term matches).
4. ``typo``: one or two keyboard slips on the canonical or a slot fill.
5. ``casing``: lower case, upper case, or bare lower case without punctuation.
6. ``accents``: accents dropped (only when the text has any).

Every item after the first has provenance ``augmented_from:<seed_id>``. Items with identical text are kept once.
"""

import random
import re
from dataclasses import dataclass, replace

from bank_agent.domain.workflow import Intent
from bank_ml.common.seeds import rng
from bank_ml.router.corpus import Lexicon, Seed
from bank_ml.router.perturb import casing, drop_accents, typo

SLOT_FILLS = 3


@dataclass(frozen=True)
class Item:
    item_id: str
    seed_id: str
    intent: Intent
    locale: str
    text: str
    provenance: str
    augmentation: str
    scope: str | None = None
    group_id: str = ""
    split: str = ""

    @property
    def language(self) -> str:
        return self.locale.split("-")[0]

    def with_split(self, group_id: str, split: str) -> "Item":
        return replace(self, group_id=group_id, split=split)


def fill(seed: Seed, lexicon: Lexicon, generator: random.Random | None) -> str:
    """The template with every slot filled: first values when ``generator`` is ``None``, else random ones."""

    def value(match: re.Match[str]) -> str:
        options = lexicon.slots[match[1]][seed.locale]
        return options[0] if generator is None else generator.choice(options[1:] or options)

    return re.sub(r"\{(\w+)\}", value, seed.template)


def slang(text: str, locale: str, lexicon: Lexicon, generator: random.Random) -> str | None:
    """The text with every matching slang term replaced, or ``None`` when no term matches."""
    table = lexicon.slang.get(locale, {})
    changed = text
    for term in sorted(table, key=len, reverse=True):
        pattern = re.compile(rf"(?<!\w){re.escape(term)}(?!\w)", re.IGNORECASE)
        if pattern.search(changed):
            changed = pattern.sub(generator.choice(list(table[term])), changed)
    return changed if changed != text else None


def augment(seed: Seed, lexicon: Lexicon) -> list[Item]:
    generator = rng("augment", seed.seed_id)
    canonical = fill(seed, lexicon, None)
    texts: list[tuple[str, str]] = [(canonical, "canonical")]
    if seed.slots:
        texts.extend((fill(seed, lexicon, generator), "slots") for _ in range(SLOT_FILLS))
    slanged = slang(canonical, seed.locale, lexicon, generator)
    if slanged is not None:
        texts.append((slanged, "slang"))
    base = generator.choice([text for text, _ in texts])
    texts.append((typo(base, generator, lexicon.keyboard, edits=generator.choice((1, 2))), "typo"))
    texts.append((casing(canonical, generator), "casing"))
    stripped = drop_accents(canonical)
    if stripped != canonical:
        texts.append((stripped, "accents"))
    items: list[Item] = []
    seen: set[str] = set()
    for text, kind in texts:
        if text in seen:
            continue
        seen.add(text)
        items.append(
            Item(
                item_id=f"{seed.seed_id}#{len(items):02d}",
                seed_id=seed.seed_id,
                intent=seed.intent,
                locale=seed.locale,
                text=text,
                provenance="team_authored" if kind == "canonical" else f"augmented_from:{seed.seed_id}",
                augmentation=kind,
                scope=seed.scope,
            )
        )
    return items
