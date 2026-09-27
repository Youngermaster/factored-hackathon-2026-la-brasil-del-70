"""Masked account and card numbers.

A ``MaskedNumber`` stores only the last four characters. The full number is read once, in ``from_full``, and
discarded, so it can never leak through a log, a prompt, or a response.
"""

from typing import Annotated, Self

from pydantic import StringConstraints

from bank_agent.domain.base import DomainModel
from bank_agent.domain.errors import InvalidMaskedNumberError

_VISIBLE = 4
_MINIMUM_LENGTH = _VISIBLE + 1


class MaskedNumber(DomainModel):
    """The last four alphanumeric characters of a product number, rendered as ``**** 1234``."""

    last4: Annotated[str, StringConstraints(pattern=r"^[0-9A-Z]{4}$")]

    @classmethod
    def from_full(cls, number: str) -> Self:
        """Keep the last four alphanumeric characters of ``number``; separators are ignored.

        A number with fewer than five alphanumeric characters raises ``InvalidMaskedNumberError``, because
        showing four of them would reveal almost all of it.
        """
        characters = [character for character in number.upper() if character.isascii() and character.isalnum()]
        if len(characters) < _MINIMUM_LENGTH:
            raise InvalidMaskedNumberError("a product number needs at least five alphanumeric characters")
        return cls(last4="".join(characters[-_VISIBLE:]))

    def __str__(self) -> str:
        return f"**** {self.last4}"
