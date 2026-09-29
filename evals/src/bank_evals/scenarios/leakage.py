"""Leakage guards for the scenario set.

- Families never cross splits (a template family belongs to one split).
- No customer text of one split is a near duplicate of a text of the other split (word 3-shingle Jaccard at or
  above ``THRESHOLD``), except the short answers every conversation shares (``yes``, an option number).
- No customer text is a near duplicate of a router training seed (``ml/corpus/router/seeds``), so the router's
  training data does not reappear in the evaluation.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Final

import yaml

from bank_agent.application.understanding.text import fold
from bank_evals.scenarios.model import Scenario

THRESHOLD: Final = 0.8
MIN_WORDS: Final = 5
SEEDS_DIR: Final = Path(__file__).resolve().parents[4] / "ml" / "corpus" / "router" / "seeds"
_PLACEHOLDER = re.compile(r"\{[a-z0-9_]+\}")


def shingles(text: str, size: int = 3) -> frozenset[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9]+", fold(text))
    return frozenset(tuple(words[i : i + size]) for i in range(max(0, len(words) - size + 1)))


def jaccard(a: frozenset[tuple[str, ...]], b: frozenset[tuple[str, ...]]) -> float:
    return len(a & b) / len(a | b) if a and b else 0.0


def customer_texts(scenario: Scenario) -> list[str]:
    """The customer's script as one text (a conversation is the unit a split holds), when it is long enough."""
    turns = scenario.turns or scenario.scripted_fallback
    script = " / ".join(t.text for t in turns if t.text is not None)
    return [script] if len(script.split()) >= MIN_WORDS else []


def near_duplicates(left: Iterable[str], right: Iterable[str]) -> list[tuple[str, str, float]]:
    right_shingles = [(text, shingles(text)) for text in right]
    found = []
    for text in left:
        mine = shingles(text)
        for other, theirs in right_shingles:
            score = jaccard(mine, theirs)
            if score >= THRESHOLD:
                found.append((text, other, score))
    return found


def cross_split(dev: Sequence[Scenario], test: Sequence[Scenario]) -> list[str]:
    problems = []
    shared = {s.template_family for s in dev} & {s.template_family for s in test}
    problems += [f"family {family} is in both splits" for family in sorted(f for f in shared if f)]
    dev_texts = {text for s in dev for text in customer_texts(s)}
    test_texts = {text for s in test for text in customer_texts(s)}
    for text, other, score in near_duplicates(sorted(dev_texts), sorted(test_texts)):
        problems.append(f"near duplicate across splits ({score:.2f}): {text!r} ~ {other!r}")
    return problems


def router_seed_texts(directory: Path = SEEDS_DIR) -> list[str]:
    texts: list[str] = []
    for path in sorted(directory.glob("*.yaml")):
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        for items in (raw.get("seeds") or {}).values():
            texts.extend(_PLACEHOLDER.sub("x", item) for item in items if isinstance(item, str))
    return texts


def against_router_seeds(scenarios: Sequence[Scenario], seeds: Sequence[str]) -> list[str]:
    texts = sorted({text for s in scenarios for text in customer_texts(s)})
    return [f"near duplicate of a router seed ({score:.2f}): {text!r} ~ {seed!r}"
            for text, seed, score in near_duplicates(texts, seeds)]  # fmt: skip
