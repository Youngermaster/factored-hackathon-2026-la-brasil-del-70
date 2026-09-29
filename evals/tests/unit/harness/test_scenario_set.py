"""The scenario set: deterministic generation, the committed files, the lint, the leakage guards, the lock."""

from functools import cache
from pathlib import Path

import pytest
from bank_evals_support import scenario

from bank_agent.domain.locale import Locale
from bank_evals.runner.subset import smoke_subset, variance_subset
from bank_evals.scenarios.generate import fill, generate
from bank_evals.scenarios.leakage import against_router_seeds, cross_split, near_duplicates, router_seed_texts
from bank_evals.scenarios.lint import lint
from bank_evals.scenarios.mix import language_plan, total
from bank_evals.scenarios.model import Scenario, ScenarioMode, Split
from bank_evals.scenarios.store import (
    LockMismatchError,
    check_lock,
    dumps,
    load_split,
    split_path,
    write_lock,
    write_split,
)
from bank_evals.world import build_world


@cache
def generated() -> dict[Split, list[Scenario]]:
    return generate(build_world())


def test_generation_is_deterministic_and_matches_the_committed_files() -> None:
    again = generate(build_world())
    for split in (Split.DEV, Split.TEST):
        assert dumps(generated()[split]) == dumps(again[split])
        assert split_path(split).read_text(encoding="utf-8") == dumps(generated()[split])
    assert generate(build_world(), "another-seed")[Split.TEST] != generated()[Split.TEST]


def test_the_committed_test_split_matches_its_lock() -> None:
    assert len(check_lock(split_path(Split.TEST))) == 64


def test_the_mix_follows_the_plan() -> None:
    assert (total(Split.TEST), total(Split.DEV)) == (332, 122)
    for split in (Split.DEV, Split.TEST):
        items = generated()[split]
        assert len(items) == total(split)
        assert lint(items, split) == []
        assert all(s.mode is ScenarioMode.SCRIPTED or s.scripted_fallback for s in items)
    test = generated()[Split.TEST]
    share = sum(s.language.value == "pt" for s in test) / len(test)
    assert 0.35 <= share <= 0.45


def test_the_lint_reports_missing_workflows_categories_and_languages() -> None:
    items = [
        s
        for s in generated()[Split.DEV]
        if not (s.workflow and s.workflow.value == "credit" and s.category.value == "normal")
    ]
    problems = lint(items, Split.DEV)
    assert any("credit: 0 normal" in p for p in problems)
    assert any("normal path lacks a language" in p for p in problems)
    orphan = scenario(workflow=None, in_scope=True)
    assert any("in scope without a workflow" in p for p in lint([orphan], Split.DEV))


def test_no_family_or_near_duplicate_crosses_the_splits_or_repeats_a_router_seed() -> None:
    assert cross_split(generated()[Split.DEV], generated()[Split.TEST]) == []
    assert against_router_seeds([*generated()[Split.DEV], *generated()[Split.TEST]], router_seed_texts()) == []
    assert near_duplicates(["no reconozco un cargo en la tienda"], ["no reconozco un cargo en la tienda"])
    leaked = generated()[Split.DEV][0].model_copy(update={"id": "leaked-001"})
    assert cross_split([leaked], generated()[Split.DEV]) != []


def test_language_plan_and_fill() -> None:
    plan = language_plan(18)
    assert (plan.count(Locale.PT_BR), {p.value for p in plan}) == (7, {"es-MX", "es-CO", "es-AR", "pt-BR"})
    assert language_plan(2).count(Locale.PT_BR) == 1
    assert fill({"a": ["{x} y {x}"]}, {"x": "1"}) == {"a": ["1 y 1"]}
    with pytest.raises(KeyError, match="unknown fact"):
        fill("{missing}", {})


def test_subsets_for_repeated_runs_and_the_smoke_suite() -> None:
    repeated = variance_subset(generated()[Split.TEST])
    assert len(repeated) == 48
    assert {s.language.value for s in repeated} == {"es", "pt"}
    smoke = smoke_subset(generated()[Split.DEV])
    assert len(smoke) == 12
    assert {s.workflow.value for s in smoke if s.workflow} == {"account_inquiry", "card_support", "dispute", "credit"}


def test_the_store_round_trips_and_the_lock_catches_a_change(tmp_path: Path) -> None:
    items = generated()[Split.DEV][:3]
    path, lock = tmp_path / "scenarios.test.jsonl", tmp_path / "test_set.lock"
    write_split(items, path)
    assert load_split(path) == sorted(items, key=lambda s: s.id)
    write_lock(path, lock)
    check_lock(path, lock)
    write_split(items[:2], path)
    with pytest.raises(LockMismatchError, match="changed"):
        check_lock(path, lock)
