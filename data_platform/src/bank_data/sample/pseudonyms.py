"""Deterministic, format-valid pseudonyms for the direct identifiers of the committed sample.

Every pseudonym is derived from ``sha256(table, column, row key, attempt)`` with no secret, so the same dataset
version always yields the same bytes. Values keep the shape the contracts check (lengths, digit positions,
country prefixes of phone numbers, date types) and are drawn so that they never equal any original value of
the same column in the sample (``avoid``): no identifier is copied verbatim.
"""

import hashlib
import unicodedata
from collections.abc import Callable, Collection
from datetime import date, timedelta

_SYLLABLES = (
    "ba", "be", "bi", "bo", "da", "de", "do", "fa", "fe", "fi", "ga", "go", "ja", "jo", "la", "le", "li",
    "lo", "lu", "ma", "me", "mi", "mo", "na", "ne", "ni", "no", "ra", "re", "ri", "ro", "sa", "se", "si",
    "so", "ta", "te", "ti", "to", "va", "ve", "vi", "za", "zo",
)  # fmt: skip
_STREETS = ("Calle", "Avenida", "Carrera", "Pasaje", "Boulevard")
_DIGITS = "0123456789"
_LETTERS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
_TEST_NETWORKS = ("192.0.2", "198.51.100", "203.0.113")
"""RFC 5737 documentation ranges: never routable, never a real customer address."""


class _Stream:
    """An endless deterministic byte stream for one ``(table, column, key, attempt)``."""

    def __init__(self, *parts: str) -> None:
        self._seed = "\x1f".join(parts).encode("utf-8")
        self._counter = 0
        self._buffer = b""

    def next_int(self, bound: int) -> int:
        if len(self._buffer) < 4:
            self._buffer += hashlib.sha256(self._seed + self._counter.to_bytes(4, "big")).digest()
            self._counter += 1
        value, self._buffer = int.from_bytes(self._buffer[:4], "big"), self._buffer[4:]
        return value % bound

    def pick(self, options: str | tuple[str, ...]) -> str:
        return options[self.next_int(len(options))]


def _draw[T](make: Callable[[_Stream], T], parts: tuple[str, ...], avoid: Collection[T]) -> T:
    for attempt in range(64):
        value = make(_Stream(*parts, str(attempt)))
        if value not in avoid:
            return value
    raise ValueError(f"no pseudonym outside the avoided values for {parts[:2]}")


def _word(stream: _Stream, syllables: int) -> str:
    return "".join(stream.pick(_SYLLABLES) for _ in range(syllables)).capitalize()


def ascii_fold(value: str) -> str:
    return unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")


def name(original: str, table: str, column: str, key: str, avoid: Collection[str]) -> str:
    """As many invented name parts as the original has (``Samuel Andrés`` becomes two parts)."""
    parts = max(1, len(original.split()))

    def make(stream: _Stream) -> str:
        return " ".join(_word(stream, 2 + stream.next_int(2)) for _ in range(parts))

    return _draw(make, (table, column, key), avoid)


def shaped(
    original: str, table: str, column: str, key: str, avoid: Collection[str], *, keep_letters: bool = False
) -> str:
    """Digits become other digits and letters other letters, in place; separators stay. For document and
    product numbers, whose format the contracts and masking rely on. ``keep_letters`` keeps prefixes such as
    ``POL-``."""

    def make(stream: _Stream) -> str:
        output = []
        for character in original:
            if character.isdigit():
                output.append(stream.pick(_DIGITS))
            elif character.isalpha() and character.isascii() and not keep_letters:
                replacement = stream.pick(_LETTERS)
                output.append(replacement if character.isupper() else replacement.lower())
            else:
                output.append(character)
        return "".join(output)

    return _draw(make, (table, column, key), avoid)


def phone(original: str, table: str, column: str, key: str, avoid: Collection[str]) -> str:
    """Keep the ``+CC`` country prefix and the grouping; replace every other digit."""
    prefix, _, rest = original.partition(" ") if original.startswith("+") else ("", "", original)

    def make(stream: _Stream) -> str:
        digits = "".join(stream.pick(_DIGITS) if character.isdigit() else character for character in rest)
        return f"{prefix} {digits}" if prefix else digits

    return _draw(make, (table, column, key), avoid)


def email(first_name: str, last_name: str, table: str, key: str, avoid: Collection[str]) -> str:
    """``<first>.<last><nn>@example.com`` from the pseudonymized names (``example.com`` is reserved)."""
    local = ".".join(ascii_fold(part).lower() for part in (first_name.split()[0], last_name.split()[0]))

    def make(stream: _Stream) -> str:
        return f"{local}{stream.next_int(100):02d}@example.com"

    return _draw(make, (table, "email", key), avoid)


def address(table: str, key: str, avoid: Collection[str]) -> str:
    def make(stream: _Stream) -> str:
        return f"{stream.pick(_STREETS)} {_word(stream, 3)} {1 + stream.next_int(999)}, Barrio {_word(stream, 3)}"

    return _draw(make, (table, "address", key), avoid)


def birth_date(original: date, table: str, key: str, avoid: Collection[date]) -> date:
    """Shift by 1 to 365 days, either way: plausible ages, never the original day."""

    def make(stream: _Stream) -> date:
        days = 1 + stream.next_int(365)
        return original + timedelta(days=days if stream.next_int(2) else -days)

    return _draw(make, (table, "date_of_birth", key), avoid)


def ip_address(table: str, key: str, avoid: Collection[str]) -> str:
    def make(stream: _Stream) -> str:
        return f"{stream.pick(_TEST_NETWORKS)}.{1 + stream.next_int(254)}"

    return _draw(make, (table, "ip_address", key), avoid)
