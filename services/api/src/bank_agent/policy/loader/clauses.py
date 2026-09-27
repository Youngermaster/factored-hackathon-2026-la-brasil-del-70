"""Clause files: parsing, path agreement, placeholders, language parity, and version order.

Current versions live at ``clauses/<family>/<CLAUSE-ID>.<lang>.md``; superseded versions, kept so that old
execution records stay resolvable, at ``clauses/<family>/superseded/<CLAUSE-ID>@<version>.<lang>.md``.
"""

import re
from collections import defaultdict
from collections.abc import Mapping

from pydantic import ValidationError

from bank_agent.domain.locale import Language
from bank_agent.domain.policy import ClauseMetadata, PolicyClause
from bank_agent.policy.loader.documents import (
    PackProblems,
    is_renderable,
    placeholders,
    split_front_matter,
    stray_braces,
)

CLAUSE_PATH = re.compile(
    r"^clauses/(?P<family>[a-z]+)/(?:(?P<superseded>superseded)/)?"
    r"(?P<id>[A-Z]+-[A-Z]+-[0-9]+(?:\.[0-9]+)*)(?:@(?P<version>[1-9][0-9]*))?\.(?P<lang>es|pt|en)\.md$"
)
_PARITY_FIELDS = ("jurisdiction", "effective_from", "params", "bound_rules")

ClauseIndex = dict[tuple[str, Language], list[PolicyClause]]


def _parse_one(path: str, text: str, problems: PackProblems) -> PolicyClause | None:
    match = CLAUSE_PATH.fullmatch(path)
    if match is None:
        problems.add(path, "a clause path is clauses/<family>/<CLAUSE-ID>.<lang>.md")
        return None
    split = split_front_matter(path, text, problems)
    if split is None:
        return None
    front, body = split
    try:
        clause = PolicyClause(metadata=ClauseMetadata.model_validate(front), body=body)
    except ValidationError as error:
        fields = sorted({".".join(str(part) for part in item["loc"]) for item in error.errors()})
        problems.add(path, f"invalid clause ({', '.join(fields) or 'body'})")
        return None
    meta = clause.metadata
    if meta.clause_id != match["id"] or meta.language.value != match["lang"]:
        problems.add(path, "the clause id and language must match the file name")
    if meta.family.value.lower() != match["family"]:
        problems.add(path, f"a {meta.family.value} clause belongs in clauses/{meta.family.value.lower()}/")
    if bool(match["superseded"]) != (match["version"] is not None):
        problems.add(path, "superseded files, and only they, carry @version in the file name")
    elif match["version"] is not None and int(match["version"]) != meta.version:
        problems.add(path, "the version in the file name must match the front matter")
    _check_body(path, clause, problems)
    return clause


def _check_body(path: str, clause: PolicyClause, problems: PackProblems) -> None:
    params = clause.metadata.params
    for name in sorted(placeholders(clause.body)):
        if name not in params:
            problems.add(path, f"placeholder {{{name}}} names no parameter of the clause")
        elif not is_renderable(params[name]):
            problems.add(path, f"placeholder {{{name}}} names a parameter that cannot be rendered")
    if stray_braces(clause.body):
        problems.add(path, "the body has a brace that is not a placeholder")


def parse_clauses(files: Mapping[str, str], languages: tuple[Language, ...], problems: PackProblems) -> ClauseIndex:
    """Parse every clause file, then check parity and version order. Versions end up ascending."""
    index: ClauseIndex = defaultdict(list)
    current: dict[tuple[str, Language], int] = {}
    for path in sorted(files):
        if not path.startswith("clauses/"):
            continue
        clause = _parse_one(path, files[path], problems)
        if clause is None:
            continue
        key = (clause.metadata.clause_id, clause.metadata.language)
        if "/superseded/" not in path:
            current[key] = clause.metadata.version
        index[key].append(clause)
    for key, versions in index.items():
        versions.sort(key=lambda clause: clause.metadata.version)
        numbers = [clause.metadata.version for clause in versions]
        if len(set(numbers)) != len(numbers):
            problems.add(key[0], f"version repeated in {key[1].value}")
        if key not in current:
            problems.add(key[0], f"no current version in {key[1].value}")
        elif numbers[-1] != current[key]:
            problems.add(key[0], "a superseded version must be lower than the current version")
    _check_parity(index, languages, problems)
    return dict(index)


def _check_parity(index: ClauseIndex, languages: tuple[Language, ...], problems: PackProblems) -> None:
    by_version: dict[tuple[str, int], dict[Language, PolicyClause]] = defaultdict(dict)
    for (clause_id, language), versions in index.items():
        for clause in versions:
            by_version[(clause_id, clause.metadata.version)][language] = clause
    for (clause_id, version), twins in sorted(by_version.items()):
        missing = [language.value for language in languages if language not in twins]
        if missing:
            problems.add(clause_id, f"version {version} has no {', '.join(missing)} twin")
            continue
        reference = twins[languages[0]]
        for language in languages[1:]:
            twin = twins[language]
            for field in _PARITY_FIELDS:
                if getattr(twin.metadata, field) != getattr(reference.metadata, field):
                    problems.add(clause_id, f"{language.value} twin differs in {field}")
            if placeholders(twin.body) != placeholders(reference.body):
                problems.add(clause_id, f"{language.value} twin has different placeholders")
