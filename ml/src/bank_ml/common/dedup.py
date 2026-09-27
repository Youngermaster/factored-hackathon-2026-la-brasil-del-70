"""Near-duplicate detection on normalized text: MinHash LSH (datasketch) for candidates, exact Jaccard to confirm.

Text is normalized (casefolded, accents and punctuation removed, digit runs replaced by ``#``, whitespace
collapsed) and cut into character ``SHINGLE``-grams. LSH proposes candidate pairs at the threshold; each candidate
is confirmed with the exact Jaccard similarity of the shingle sets, so the result does not depend on LSH's
probabilistic misses in the confirming step (a pair LSH never proposes can still be missed; the guard test
therefore also runs an exact scan on the router corpus, which is small).

Thresholds (documented in the dataset cards): ``SEED_MERGE_THRESHOLD`` merges seeds into one seed group before
splitting; ``CROSS_SPLIT_THRESHOLD`` removes dev and test items that are near-duplicates of train items.
"""

import re
import unicodedata
from collections.abc import Iterable, Mapping, Sequence

from datasketch import MinHash, MinHashLSH

from bank_ml.common.seeds import GLOBAL_SEED

SHINGLE = 4
NUM_PERM = 128
SEED_MERGE_THRESHOLD = 0.6
CROSS_SPLIT_THRESHOLD = 0.8
LSH_MARGIN = 0.1
_NON_WORD = re.compile(r"[^a-z0-9# ]+")
_DIGITS = re.compile(r"[0-9]+")
_SPACES = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    stripped = "".join(character for character in decomposed if not unicodedata.combining(character))
    masked = _DIGITS.sub("#", stripped)
    return _SPACES.sub(" ", _NON_WORD.sub(" ", masked)).strip()


def shingles(text: str, size: int = SHINGLE) -> frozenset[str]:
    normalized = normalize_text(text)
    if len(normalized) <= size:
        return frozenset({normalized})
    return frozenset(normalized[start : start + size] for start in range(len(normalized) - size + 1))


def jaccard(left: frozenset[str], right: frozenset[str]) -> float:
    if not left and not right:
        return 1.0
    return len(left & right) / len(left | right)


def _lsh(threshold: float) -> MinHashLSH:
    """An index proposing candidates a little below ``threshold`` (fewer misses; exact Jaccard confirms)."""
    return MinHashLSH(threshold=min(0.9, max(0.1, threshold - LSH_MARGIN)), num_perm=NUM_PERM)


def _minhash(values: Iterable[str]) -> MinHash:
    signature = MinHash(num_perm=NUM_PERM, seed=GLOBAL_SEED)
    for value in sorted(values):
        signature.update(value.encode("utf-8"))
    return signature


def near_duplicate_pairs(texts: Mapping[str, str], threshold: float) -> list[tuple[str, str, float]]:
    """Confirmed pairs ``(key_a, key_b, jaccard)`` with ``key_a < key_b`` among ``texts`` (key -> text)."""
    sets = {key: shingles(text) for key, text in texts.items()}
    lsh = _lsh(threshold)
    signatures = {key: _minhash(values) for key, values in sets.items()}
    for key in sorted(signatures):
        lsh.insert(key, signatures[key])
    pairs: set[tuple[str, str]] = set()
    for key in sorted(signatures):
        for other in lsh.query(signatures[key]):
            if other != key:
                pairs.add((min(key, other), max(key, other)))
    confirmed = [(a, b, jaccard(sets[a], sets[b])) for a, b in sorted(pairs)]
    return [(a, b, score) for a, b, score in confirmed if score >= threshold]


def cluster(keys: Sequence[str], pairs: Iterable[tuple[str, str, float]]) -> dict[str, str]:
    """Union-find over ``pairs``: every key maps to the smallest key of its connected component."""
    parent = {key: key for key in keys}

    def find(key: str) -> str:
        while parent[key] != key:
            parent[key] = parent[parent[key]]
            key = parent[key]
        return key

    for left, right, _ in pairs:
        root_left, root_right = find(left), find(right)
        if root_left != root_right:
            parent[max(root_left, root_right)] = min(root_left, root_right)
    return {key: find(key) for key in keys}


def cross_split_duplicates(
    reference: Mapping[str, str], candidates: Mapping[str, str], threshold: float
) -> dict[str, tuple[str, float]]:
    """Candidate keys that are near-duplicates of some reference key: ``{candidate: (reference, jaccard)}``."""
    ref_sets = {key: shingles(text) for key, text in reference.items()}
    lsh = _lsh(threshold)
    for key in sorted(ref_sets):
        lsh.insert(key, _minhash(ref_sets[key]))
    found: dict[str, tuple[str, float]] = {}
    for key in sorted(candidates):
        values = shingles(candidates[key])
        best: tuple[str, float] | None = None
        for other in sorted(lsh.query(_minhash(values))):
            score = jaccard(values, ref_sets[other])
            if score >= threshold and (best is None or score > best[1]):
                best = (other, score)
        if best is not None:
            found[key] = best
    return found


def exact_cross_split_max(reference: Iterable[str], candidates: Iterable[str]) -> float:
    """The largest exact Jaccard between any candidate and any reference text (a brute-force check for tests)."""
    ref_sets = [shingles(text) for text in reference]
    best = 0.0
    for text in candidates:
        values = shingles(text)
        best = max([best, *(jaccard(values, other) for other in ref_sets)])
    return best
