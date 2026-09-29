"""Deterministic scenario generation from the family files and the evaluation world (``generate``).

Per cell (a workflow and a category, or a routing kind): the phrasings of the cell's situations are ordered by a
seeded hash; dev takes its share, one phrasing per situation first, so every situation has dev coverage when it
has two or more phrasings; test takes the rest. Each split's slots follow the language plan (40% pt-BR, Spanish
even across es-MX, es-CO, es-AR), and each slot renders the next phrasing for a persona of the slot's country (for
pt-BR, rotating countries). The same seed always gives the same bytes.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Sequence
from typing import Any, Final

from bank_agent.domain.locale import Locale
from bank_evals.scenarios.facts import persona_facts
from bank_evals.scenarios.families import FAMILY_FILES, Phrasing, Situation, TurnSpec, load_situations
from bank_evals.scenarios.mix import (
    DIRECT_INJECTION_TAG,
    PER_WORKFLOW,
    ROUTING,
    ROUTING_TAG,
    SIMULATED_CATEGORIES,
    language_plan,
)
from bank_evals.scenarios.model import Provenance, Scenario, ScenarioCategory, ScenarioMode, Split
from bank_evals.world.model import World

DEFAULT_SEED: Final = "bank-eval-scenarios-v1"
COUNTRY_OF: Final = {Locale.ES_MX: "MX", Locale.ES_CO: "CO", Locale.ES_AR: "AR"}
PT_COUNTRIES: Final = ("MX", "CO", "AR")
_PLACEHOLDER: Final = re.compile(r"\{([a-z0-9_]+)\}")
ROUTING_KINDS: Final = {"out_of_scope": "oos", "switch": "switch"}


def _hash(seed: str, key: str) -> str:
    return hashlib.sha256(f"{seed}:{key}".encode()).hexdigest()


def fill(value: Any, facts: dict[str, str]) -> Any:
    """Replace ``{fact}`` placeholders in strings, recursively; an unknown fact is an error."""
    if isinstance(value, str):

        def replace(match: re.Match[str]) -> str:
            if match[1] not in facts:
                raise KeyError(f"unknown fact {match[1]!r}")
            return facts[match[1]]

        return _PLACEHOLDER.sub(replace, value)
    if isinstance(value, list):
        return [fill(item, facts) for item in value]
    if isinstance(value, dict):
        return {key: fill(item, facts) for key, item in value.items()}
    return value


def _turn(spec: TurnSpec, facts: dict[str, str]) -> dict[str, Any]:
    if isinstance(spec, str):
        return {"text": fill(spec, facts)}
    if "option" in spec:
        return {"action": "select_option", "option_index": spec["option"]}
    return {key: fill(item, facts) for key, item in spec.items()}


def _texts(phrasing: Phrasing, dialect: Locale) -> list[TurnSpec]:
    if dialect is Locale.PT_BR:
        return phrasing.pt
    if dialect is Locale.ES_AR and phrasing.es_ar is not None:
        return phrasing.es_ar
    return phrasing.es


def _uses_record_facts(situation: Situation, phrasing: Phrasing) -> bool:
    text = str(phrasing.model_dump()) + str(situation.required) + str(situation.fixtures)
    return bool(_PLACEHOLDER.search(text))


def split_phrasings(situations: Sequence[Situation], seed: str, dev_share: float, workflow: str) -> dict[Split, list[
        tuple[Situation, int, Phrasing]]]:  # fmt: skip
    """Assign each (situation, phrasing) to dev or test; dev first takes one phrasing per situation."""
    items = [(s, i, p) for s in situations for i, p in enumerate(s.phrasings)]
    items.sort(key=lambda item: _hash(seed, item[0].family_key(workflow, item[1])))
    dev_count = max(1, round(len(items) * dev_share)) if len(items) > 1 else 0
    dev: list[tuple[Situation, int, Phrasing]] = []
    seen: set[str] = set()
    for item in items:
        if len(dev) < dev_count and item[0].key not in seen and len(item[0].phrasings) > 1:
            dev.append(item)
            seen.add(item[0].key)
    for item in items:
        if len(dev) < dev_count and item not in dev:
            dev.append(item)
    return {Split.DEV: dev, Split.TEST: [item for item in items if item not in dev]}


def render_cell(
    world: World,
    items: Sequence[tuple[Situation, int, Phrasing]],
    count: int,
    split: Split,
    workflow: str,
    id_prefix: str,
) -> list[Scenario]:
    """``count`` scenarios of one cell and split, following the language plan."""
    if count and not items:
        raise ValueError(f"{id_prefix}: no phrasings for {count} {split.value} scenarios")
    used: set[tuple[int, str, str]] = set()
    rendered: list[Scenario] = []
    cursor = 0
    for number, dialect in enumerate(language_plan(count), start=1):
        for attempt in range(len(items) * len(PT_COUNTRIES) + 1):
            index = (cursor + attempt) % len(items)
            situation, phrasing_index, phrasing = items[index]
            countries = [COUNTRY_OF[dialect]] if dialect in COUNTRY_OF else list(PT_COUNTRIES)
            options = [c for c in countries if c in situation.countries and (index, dialect.value, c) not in used]
            if options:
                country = options[(number + index) % len(options)]
                used.add((index, dialect.value, country))
                cursor = index + 1
                break
        else:
            raise ValueError(f"{id_prefix}: not enough phrasings for {count} {split.value} scenarios")
        rendered.append(_scenario(world, situation, phrasing_index, phrasing, dialect, country, split,
                                  f"{id_prefix}-{number:03d}", workflow))  # fmt: skip
    return rendered


def _scenario(world: World, situation: Situation, phrasing_index: int, phrasing: Phrasing, dialect: Locale,
              country: str, split: Split, scenario_id: str, workflow: str) -> Scenario:  # fmt: skip
    persona_ref = f"{situation.role}-{country.lower()}"
    facts = persona_facts(world, persona_ref, dialect.language.value)
    turns = [_turn(spec, facts) for spec in _texts(phrasing, dialect)]
    if situation.category is ScenarioCategory.AMBIGUOUS:
        # Answers to a clarifying question are sent only when the system asks one.
        turns = [turn if index == 0 or "text" not in turn else {**turn, "when_asked": True}
                 for index, turn in enumerate(turns)]  # fmt: skip
    simulated = situation.category in SIMULATED_CATEGORIES or (
        situation.category is ScenarioCategory.PROMPT_INJECTION and DIRECT_INJECTION_TAG in situation.tags
    )
    provenance = situation.provenance or (
        Provenance.DERIVED_FROM_RECORD if _uses_record_facts(situation, phrasing) else Provenance.TEAM_GENERATED
    )
    document: dict[str, Any] = {
        "id": scenario_id, "split": split.value, "language": dialect.language.value, "dialect": dialect.value,
        "category": situation.category.value, "tags": sorted({*situation.tags}), "persona_ref": persona_ref,
        "goal": fill(situation.goal, facts), "known_facts": fill(situation.known_facts, facts),
        "hidden_facts": fill(situation.hidden_facts, facts),
        "mode": ScenarioMode.SIMULATED.value if simulated else ScenarioMode.SCRIPTED.value,
        "fixtures": fill(situation.fixtures, facts), "tool_failure_plan": situation.tool_failure_plan,
        "expected_outcome": situation.expected_outcome.value,
        "expected_state_assertions": fill(situation.assertions, facts),
        "required_disclosures": fill(situation.required, facts),
        "forbidden_disclosures": fill(situation.forbidden, facts),
        "expected_handoff_fields": situation.handoff_fields, "in_scope": situation.in_scope,
        "provenance": provenance.value, "workflow": situation.workflow.value if situation.workflow else None,
        "expected_workflow_path": [w.value for w in situation.expected_workflow_path],
        "expected_eligibility_outcome": situation.eligibility.value if situation.eligibility else None,
        "template_family": situation.family_key(workflow, phrasing_index),
    }  # fmt: skip
    if simulated:
        document["simulator_instructions"] = fill(situation.simulate or situation.goal, facts)
        document["scripted_fallback"] = turns
    else:
        document["turns"] = turns
    return Scenario.model_validate(document)


def generate(world: World, seed: str = DEFAULT_SEED) -> dict[Split, list[Scenario]]:
    """Every scenario of both splits, deterministically."""
    out: dict[Split, list[Scenario]] = {Split.DEV: [], Split.TEST: []}
    for name in FAMILY_FILES:
        situations = load_situations(name)
        cells: list[tuple[str, list[Situation], dict[Split, int]]] = []
        if name == "routing":
            for kind, short in ROUTING_KINDS.items():
                chosen = [s for s in situations if (s.workflow is None) == (kind == "out_of_scope")]
                cells.append((f"rtg-{short}", chosen, {split: ROUTING[split][kind] for split in out}))
        else:
            for category in PER_WORKFLOW[Split.TEST]:
                chosen = [s for s in situations if s.category is category]
                cells.append((f"{name[:3]}-{category.value[:8]}", chosen,
                              {split: PER_WORKFLOW[split][category] for split in out}))  # fmt: skip
        for prefix, chosen, counts in cells:
            share = counts[Split.DEV] / (counts[Split.DEV] + counts[Split.TEST])
            parts = split_phrasings(chosen, seed, share, name)
            for split in (Split.DEV, Split.TEST):
                id_prefix = f"{split.value}-{prefix}".replace("_", "-")
                out[split].extend(render_cell(world, parts[split], counts[split], split, name, id_prefix))
    for split in out:
        out[split] = [s.model_copy(update={"tags": tuple(sorted({*s.tags, ROUTING_TAG}))})
                      if s.id.split("-")[1] == "rtg" else s for s in out[split]]  # fmt: skip
    return out
