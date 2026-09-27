"""Fixed seeds. Every random choice in ``bank_ml`` derives from ``GLOBAL_SEED`` and a stable key, so a rerun on the
same inputs makes the same choices on any machine (Python's ``hash`` is salted per process and is never used)."""

import hashlib
import random

GLOBAL_SEED = 20260927


def seed_for(*parts: object) -> int:
    """A 32-bit seed from ``GLOBAL_SEED`` and ``parts`` (stable across processes and platforms)."""
    key = "\x1f".join([str(GLOBAL_SEED), *(str(part) for part in parts)])
    return int.from_bytes(hashlib.sha256(key.encode("utf-8")).digest()[:4], "big")


def rng(*parts: object) -> random.Random:
    """A ``random.Random`` seeded from ``parts``; not for security (S311 is expected here)."""
    return random.Random(seed_for(*parts))  # noqa: S311  # nosec B311 (reproducible sampling, not security)
