"""Load and validate a policy pack from the text of its files (``policies/``), with no I/O of its own.

The filesystem adapter reads the files into a mapping of relative path to text and calls ``load_pack``. Every
problem is collected and reported together in one ``PolicyPackInvalidError``.
"""

import hashlib
from collections.abc import Mapping

from bank_agent.domain.errors import PolicyPackInvalidError
from bank_agent.domain.locale import Language
from bank_agent.policy.loader.clauses import parse_clauses
from bank_agent.policy.loader.documents import PackProblems
from bank_agent.policy.loader.lock import check_lock
from bank_agent.policy.loader.rules_check import check_rule_parameters
from bank_agent.policy.loader.structure import parse_bindings, parse_info, parse_matrix, parse_messages
from bank_agent.policy.pack import PolicyPack

EXCLUDED_FROM_VERSION = frozenset({"README.md"})
MAX_REPORTED_PROBLEMS = 25


def pack_version(files: Mapping[str, str]) -> str:
    """``pack-`` and 16 hex digits of a SHA-256 over every pack file except the README, in path order."""
    digest = hashlib.sha256()
    for path in sorted(files):
        if path in EXCLUDED_FROM_VERSION:
            continue
        digest.update(f"{path}\n".encode())
        digest.update(files[path].replace("\r\n", "\n").encode())
        digest.update(b"\n")
    return f"pack-{digest.hexdigest()[:16]}"


def load_pack(files: Mapping[str, str], *, check_versions: bool = True) -> PolicyPack:
    """Build a validated pack. ``check_versions=False`` skips the lock check (used only to write a new lock)."""
    problems = PackProblems()
    info = parse_info(files, problems)
    languages = info.languages if info is not None else tuple(Language)
    clauses = parse_clauses(files, languages, problems)
    bindings = parse_bindings(files, {clause_id for clause_id, _ in clauses}, problems)
    matrix = parse_matrix(files, bindings, problems)
    messages = parse_messages(files, languages, problems)
    if check_versions:
        check_lock(files, problems)
    if info is not None and bindings is not None:
        check_rule_parameters(clauses, messages, problems)
    if problems or info is None or bindings is None:
        shown = problems.items[:MAX_REPORTED_PROBLEMS]
        more = len(problems.items) - len(shown)
        suffix = f"; and {more} more" if more > 0 else ""
        raise PolicyPackInvalidError("invalid policy pack: " + "; ".join(shown) + suffix)
    return PolicyPack(
        version=pack_version(files),
        info=info,
        clauses=clauses,
        bindings=bindings,
        matrix=matrix,
        messages=messages,
    )
