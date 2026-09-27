"""Predictable identifiers."""

from collections import Counter

from bank_agent.domain.identifiers import IdKind


class SequentialIdGenerator:
    """Implements the ``IdGenerator`` port: ``case-000001``, ``case-000002``, with one counter per kind."""

    def __init__(self) -> None:
        self._counters: Counter[IdKind] = Counter()

    def new(self, kind: IdKind) -> str:
        self._counters[kind] += 1
        return f"{kind.value}-{self._counters[kind]:06d}"
