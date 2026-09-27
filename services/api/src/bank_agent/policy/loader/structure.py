"""The pack's structural files: ``pack.yaml``, ``bindings.yaml``, ``matrix.yaml``, and the message files."""

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ValidationError

from bank_agent.domain.actions import ActionKind
from bank_agent.domain.eligibility import EligibilityOutcome, ReviewPath, UncertaintyStatement
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.policy import ActionRequirement
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_agent.policy.loader.documents import PackProblems, load_yaml
from bank_agent.policy.pack import Bindings, PackInfo

PACK_INFO_PATH = "pack.yaml"
BINDINGS_PATH = "bindings.yaml"
MATRIX_PATH = "matrix.yaml"
MESSAGE_GROUPS = ("outcome", "reason", "missing_fact", "uncertainty", "review_path", "heading")
_REQUIRED_MESSAGES: dict[str, tuple[str, ...]] = {
    "outcome": tuple(EligibilityOutcome),
    "uncertainty": tuple(UncertaintyStatement),
    "review_path": tuple(ReviewPath),
    "heading": ("reasons", "missing", "synthetic_notice"),
}

Messages = dict[Language, dict[str, dict[str, str]]]


def _model[M: BaseModel](model: type[M], path: str, data: Any, problems: PackProblems) -> M | None:
    try:
        return model.model_validate(data)
    except ValidationError as error:
        fields = sorted({".".join(str(part) for part in item["loc"]) for item in error.errors()})
        problems.add(path, f"invalid ({', '.join(fields) or 'document'})")
        return None


def parse_info(files: Mapping[str, str], problems: PackProblems) -> PackInfo | None:
    if PACK_INFO_PATH not in files:
        problems.add(PACK_INFO_PATH, "missing")
        return None
    return _model(PackInfo, PACK_INFO_PATH, load_yaml(PACK_INFO_PATH, files[PACK_INFO_PATH], problems), problems)


def parse_bindings(files: Mapping[str, str], known: set[str], problems: PackProblems) -> Bindings | None:
    """Parse the bindings: exactly the registered states of every workflow, and every resolved clause id exists."""
    if BINDINGS_PATH not in files:
        problems.add(BINDINGS_PATH, "missing")
        return None
    bindings = _model(Bindings, BINDINGS_PATH, load_yaml(BINDINGS_PATH, files[BINDINGS_PATH], problems), problems)
    if bindings is None:
        return None
    for descriptor in WORKFLOW_CATALOG.descriptors:
        states = bindings.workflows.get(descriptor.id)
        if states is None:
            problems.add(BINDINGS_PATH, f"workflow {descriptor.id} has no bindings")
            continue
        for state in descriptor.states:
            if state not in states:
                problems.add(BINDINGS_PATH, f"workflow {descriptor.id} has no binding for its state {state}")
        for state in states:
            if state not in descriptor.states:
                problems.add(BINDINGS_PATH, f"workflow {descriptor.id} has no state {state}")
            for country in Country:
                for clause_id in bindings.clause_ids(descriptor.id, state, country):
                    if clause_id not in known:
                        problems.add(BINDINGS_PATH, f"{descriptor.id}.{state} names unknown clause {clause_id}")
    return bindings


def parse_matrix(
    files: Mapping[str, str], bindings: Bindings | None, problems: PackProblems
) -> dict[ActionKind, ActionRequirement]:
    """One row per action; a workflow may appear only if it owns the action, with states it has bindings for."""
    data = load_yaml(MATRIX_PATH, files.get(MATRIX_PATH, ""), problems)
    rows = data.get("actions") if isinstance(data, dict) else None
    if not isinstance(rows, list):
        problems.add(MATRIX_PATH, "the matrix has an actions list")
        return {}
    matrix: dict[ActionKind, ActionRequirement] = {}
    for row in rows:
        requirement = _model(ActionRequirement, MATRIX_PATH, row, problems)
        if requirement is None:
            continue
        if requirement.action in matrix:
            problems.add(MATRIX_PATH, f"action {requirement.action} appears twice")
        matrix[requirement.action] = requirement
        for workflow, states in requirement.allowed_states.items():
            if requirement.action not in WORKFLOW_CATALOG.descriptor(workflow).write_actions:
                problems.add(MATRIX_PATH, f"workflow {workflow} does not own action {requirement.action}")
            known_states = bindings.workflows.get(workflow, {}) if bindings is not None else {}
            for state in states:
                if state not in known_states:
                    problems.add(MATRIX_PATH, f"{requirement.action} names unbound state {workflow}.{state}")
    for action in ActionKind:
        if action not in matrix:
            problems.add(MATRIX_PATH, f"no row for action {action}")
    return matrix


def parse_messages(files: Mapping[str, str], languages: tuple[Language, ...], problems: PackProblems) -> Messages:
    """Parse ``messages/eligibility.<lang>.yaml``; every language must have the same groups and keys."""
    messages: Messages = {}
    for language in languages:
        path = f"messages/eligibility.{language.value}.yaml"
        data = load_yaml(path, files.get(path, ""), problems) if path in files else None
        if not isinstance(data, dict) or set(data) != set(MESSAGE_GROUPS):
            problems.add(path, f"needs exactly the groups {', '.join(MESSAGE_GROUPS)}")
            continue
        groups: dict[str, dict[str, str]] = {}
        for group, entries in data.items():
            if not isinstance(entries, dict) or not all(isinstance(v, str) and v.strip() for v in entries.values()):
                problems.add(path, f"group {group} maps keys to non-empty text")
                continue
            groups[str(group)] = {str(key): value.strip() for key, value in entries.items()}
        for group, keys in _REQUIRED_MESSAGES.items():
            missing = sorted(set(keys) - set(groups.get(group, {})))
            if missing:
                problems.add(path, f"group {group} lacks {', '.join(missing)}")
        messages[language] = groups
    if len(messages) == len(languages) and languages:
        reference = messages[languages[0]]
        for language in languages[1:]:
            for group in MESSAGE_GROUPS:
                if set(messages[language].get(group, {})) != set(reference.get(group, {})):
                    path = f"messages/eligibility.{language.value}.yaml"
                    problems.add(path, f"group {group} keys differ from {languages[0].value}")
    return messages
