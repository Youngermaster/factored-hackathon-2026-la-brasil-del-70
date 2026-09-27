"""Deterministic text perturbations: typing noise for training augmentation, speech-to-text noise for the
robustness set. Every function takes its randomness from an explicit ``random.Random`` (seeded by the caller from a
stable key) or none at all, so the same input always gives the same output."""

import math
import random
import re
import unicodedata
from collections.abc import Mapping, Sequence

_PUNCTUATION = re.compile(r"[¿?¡!.,;:\"()]")
_SPACES = re.compile(r"\s+")


def drop_accents(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    kept = "".join(character for character in decomposed if not unicodedata.combining(character))
    return unicodedata.normalize("NFC", kept)


def strip_punctuation(text: str) -> str:
    return _SPACES.sub(" ", _PUNCTUATION.sub(" ", text)).strip()


def replace_words(text: str, table: Mapping[str, str]) -> str:
    """Whole-word, case-insensitive replacements, longest key first."""
    for key in sorted(table, key=len, reverse=True):
        text = re.sub(rf"(?<!\w){re.escape(key)}(?!\w)", table[key], text, flags=re.IGNORECASE)
    return text


def typo(text: str, generator: random.Random, keyboard: Mapping[str, str], edits: int = 1) -> str:
    """``edits`` keyboard slips on letters: a neighbour key, a dropped letter, a doubled letter, or a swap."""
    characters = list(text)
    for _ in range(edits):
        letters = [index for index, character in enumerate(characters) if character.lower() in keyboard]
        if not letters:
            break
        index = generator.choice(letters)
        kind = generator.choice(("neighbour", "drop", "double", "swap"))
        if kind == "neighbour":
            characters[index] = generator.choice(keyboard[characters[index].lower()])
        elif kind == "drop" and len(characters) > 3:
            del characters[index]
        elif kind == "double":
            characters.insert(index, characters[index])
        elif index + 1 < len(characters):
            characters[index], characters[index + 1] = characters[index + 1], characters[index]
    return "".join(characters)


def casing(text: str, generator: random.Random) -> str:
    """All lower case, all upper case, or lower case without punctuation."""
    kind = generator.choice(("lower", "upper", "bare"))
    if kind == "lower":
        return text.lower()
    if kind == "upper":
        return text.upper()
    return strip_punctuation(text.lower())


def add_fillers(text: str, fillers: Sequence[str], generator: random.Random, count: int = 2) -> str:
    words = text.split()
    for _ in range(count):
        words.insert(generator.randrange(0, len(words) + 1), generator.choice(fillers))
    return " ".join(words)


def truncate(text: str, share: float = 0.6) -> str:
    """The first ``share`` of the words (at least two), as when a recording is cut."""
    words = text.split()
    keep = max(2, math.ceil(len(words) * share))
    return " ".join(words[:keep])


def speech_to_text(text: str, homophones: Mapping[str, str], fillers: Sequence[str], generator: random.Random) -> str:
    """A transcript-style rendering: homophones, fillers, lower case, and no accents or punctuation."""
    replaced = replace_words(text, homophones)
    return drop_accents(strip_punctuation(add_fillers(replaced, fillers, generator, count=1).lower()))
