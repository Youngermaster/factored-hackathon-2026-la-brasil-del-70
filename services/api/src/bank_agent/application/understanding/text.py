"""Text folding shared by the detectors and parsers: casefold and strip accents, keep letters, digits, and spaces."""

import re
import unicodedata

_SPACES = re.compile(r"\s+")
_WORD = re.compile(r"[a-z0-9]+")


def fold(text: str) -> str:
    """Casefold, drop combining marks, and collapse whitespace (``Cartão  bloqueado`` -> ``cartao bloqueado``)."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(character for character in decomposed if not unicodedata.combining(character))
    return _SPACES.sub(" ", stripped).strip()


def words(text: str) -> list[str]:
    """The folded alphanumeric words of ``text``."""
    return _WORD.findall(fold(text))
