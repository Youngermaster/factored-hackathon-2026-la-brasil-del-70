"""The router's text analyzer, shared by training (``bank-ml``) and serving (``router:tfidf``) so they cannot skew.

``router_terms`` turns a message into terms: folded words (``w:``), word bigrams (``w:a_b``), and character 2- to
5-grams over the folded, space-padded word sequence (``c:``). Digit runs become ``#`` so amounts and card endings do
not become vocabulary. ``ANALYZER_ID`` names this exact behavior; an artifact records it and the adapter refuses an
artifact built with another analyzer.
"""

import math
import re
from collections import Counter
from collections.abc import Mapping, Sequence
from itertools import pairwise

from bank_agent.application.understanding.text import fold

ANALYZER_ID = "router_terms@1"
CHAR_NGRAMS = (2, 3, 4, 5)
_TOKEN = re.compile(r"[a-z#]+")
_DIGITS = re.compile(r"[0-9]+")


def normalize(text: str) -> str:
    """Folded text with digit runs replaced by ``#``: the input of every term."""
    return _DIGITS.sub("#", fold(text))


def tokens(text: str) -> list[str]:
    return _TOKEN.findall(normalize(text))


def router_terms(text: str) -> list[str]:
    """Every term of ``text``, with repetitions (term frequency is counted by the caller)."""
    words = tokens(text)
    terms = [f"w:{word}" for word in words]
    terms.extend(f"w:{left}_{right}" for left, right in pairwise(words))
    padded = f" {' '.join(words)} "
    for size in CHAR_NGRAMS:
        terms.extend(f"c:{padded[start : start + size]}" for start in range(len(padded) - size + 1))
    return terms


def tfidf_vector(text: str, index: Mapping[str, int], idf: Sequence[float]) -> dict[int, float]:
    """Sublinear, L2-normalized TF-IDF weights of the known terms of ``text``, as ``{term index: weight}``.

    Matches scikit-learn's ``TfidfVectorizer(sublinear_tf=True, norm="l2")`` over ``router_terms``.
    """
    counts = Counter(term for term in router_terms(text) if term in index)
    weights = {index[term]: (1.0 + math.log(count)) * idf[index[term]] for term, count in counts.items()}
    norm = math.sqrt(sum(value * value for value in weights.values()))
    if norm == 0.0:
        return {}
    return {position: value / norm for position, value in weights.items()}


def softmax(logits: Sequence[float], temperature: float = 1.0) -> list[float]:
    """Numerically stable softmax of ``logits / temperature``."""
    scaled = [value / temperature for value in logits]
    top = max(scaled)
    exps = [math.exp(value - top) for value in scaled]
    total = sum(exps)
    return [value / total for value in exps]
