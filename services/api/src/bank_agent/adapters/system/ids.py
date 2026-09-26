"""Random identifiers."""

import secrets

from bank_agent.domain.identifiers import IdKind

_RANDOM_BYTES = 16


class RandomIdGenerator:
    """Implements the ``IdGenerator`` port: the kind prefix plus 128 random bits in hex, for example
    ``case-3f2a...``. Identifiers are unguessable, so they reveal nothing about volume or order."""

    def new(self, kind: IdKind) -> str:
        return f"{kind.value}-{secrets.token_hex(_RANDOM_BYTES)}"
