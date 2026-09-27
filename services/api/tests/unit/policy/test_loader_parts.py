"""The pure loader's parts, on small in-memory file sets (no filesystem)."""

from typing import Any

import pytest

from bank_agent.domain.errors import PolicyPackInvalidError
from bank_agent.domain.locale import Language
from bank_agent.policy.loader import load_pack, pack_version
from bank_agent.policy.loader.clauses import parse_clauses
from bank_agent.policy.loader.documents import PackProblems, load_yaml, split_front_matter, stray_braces
from bank_agent.policy.loader.lock import check_lock, current_digests, render_lock

LANGS = (Language.ES, Language.PT, Language.EN)


def clause_file(
    clause_id: str = "DSP-CO-1",
    language: str = "es",
    *,
    version: int = 1,
    params: str = "  dispute_window_days: 60\n",
    body: str = "Plazo de {dispute_window_days} días.",
) -> str:
    jurisdiction = clause_id.split("-")[1]
    return (
        f"---\nclause_id: {clause_id}\nversion: {version}\njurisdiction: {jurisdiction}\nlanguage: {language}\n"
        f"effective_from: 2026-09-27\nsynthetic: true\nparams:\n{params}bound_rules: [DSP.within_window]\n"
        f"summary: Fixture.\n---\n{body}\n"
    )


def twins(**kwargs: Any) -> dict[str, str]:
    return {f"clauses/dsp/DSP-CO-1.{lang}.md": clause_file(language=lang, **kwargs) for lang in ("es", "pt", "en")}


def problems_of(files: dict[str, str]) -> list[str]:
    problems = PackProblems()
    parse_clauses(files, LANGS, problems)
    return problems.items


def test_valid_twins_parse_without_problems() -> None:
    assert problems_of(twins()) == []


def test_a_missing_twin_and_a_parameter_difference_are_reported() -> None:
    files = twins()
    del files["clauses/dsp/DSP-CO-1.en.md"]
    files["clauses/dsp/DSP-CO-1.pt.md"] = clause_file(language="pt", params="  dispute_window_days: 61\n")
    found = " ".join(problems_of(files))
    assert "no en twin" in found


def test_parity_checks_params_and_placeholders() -> None:
    files = twins()
    files["clauses/dsp/DSP-CO-1.pt.md"] = clause_file(language="pt", params="  dispute_window_days: 61\n")
    files["clauses/dsp/DSP-CO-1.en.md"] = clause_file(language="en", body="A window of some days.")
    found = " ".join(problems_of(files))
    assert "pt twin differs in params" in found
    assert "en twin has different placeholders" in found


@pytest.mark.parametrize(
    ("body", "message"),
    [
        ("Plazo de {unknown} días.", "names no parameter"),
        ("Plazo de {dispute_window_days} días {", "brace"),
    ],
)
def test_placeholders_must_resolve(body: str, message: str) -> None:
    assert message in " ".join(problems_of(twins(body=body)))


def test_list_parameters_cannot_be_placeholders() -> None:
    files = twins(params="  codes: [a, b]\n", body="Codes {codes}.")
    assert "cannot be rendered" in " ".join(problems_of(files))


def test_paths_must_match_the_front_matter() -> None:
    files = {"clauses/acc/DSP-CO-1.es.md": clause_file(), "clauses/dsp/bad-name.md": "x"}
    found = " ".join(problems_of(files))
    assert "belongs in clauses/dsp/" in found
    assert "a clause path is" in found


def test_superseded_versions_must_be_lower_than_the_current_one() -> None:
    files = twins(version=2)
    for lang in ("es", "pt", "en"):
        files[f"clauses/dsp/superseded/DSP-CO-1@3.{lang}.md"] = clause_file(language=lang, version=3)
    assert "superseded version must be lower" in " ".join(problems_of(files))


def test_front_matter_and_yaml_errors_are_recorded() -> None:
    problems = PackProblems()
    assert split_front_matter("x.md", "no front matter", problems) is None
    assert load_yaml("x.yaml", "a: [unclosed", problems) is None
    assert len(problems.items) == 2
    assert stray_braces("{ok} }")


def test_the_lock_detects_a_change_without_a_version_bump() -> None:
    files = twins()
    files["versions.lock.yaml"] = render_lock(files)
    problems = PackProblems()
    check_lock(files, problems)
    assert problems.items == []
    files["clauses/dsp/DSP-CO-1.es.md"] = clause_file(body="Otro plazo de {dispute_window_days} días.")
    check_lock(files, problems)
    assert "without a version bump" in " ".join(problems.items)
    with pytest.raises(ValueError, match="bump the clause version"):
        render_lock(files)


def test_a_bumped_version_makes_the_lock_stale_until_it_is_rewritten() -> None:
    files = twins()
    files["versions.lock.yaml"] = render_lock(files)
    files.update(twins(version=2, body="Nuevo plazo de {dispute_window_days} días."))
    problems = PackProblems()
    check_lock(files, problems)
    assert "stale" in " ".join(problems.items)
    files["versions.lock.yaml"] = render_lock(files)
    assert current_digests(files)["DSP-CO-1"][0] == 2


def test_a_lower_version_than_the_lock_is_rejected() -> None:
    files = twins(version=2)
    files["versions.lock.yaml"] = render_lock(files)
    files.update(twins(version=1))
    problems = PackProblems()
    check_lock(files, problems)
    assert "lower than the locked version" in " ".join(problems.items)


def test_an_empty_pack_reports_every_missing_part() -> None:
    with pytest.raises(PolicyPackInvalidError) as error:
        load_pack({})
    message = str(error.value)
    assert "pack.yaml: missing" in message
    assert "bindings.yaml: missing" in message


def test_the_pack_version_ignores_the_readme_and_line_endings() -> None:
    files = twins()
    assert pack_version(files) == pack_version({**files, "README.md": "anything"})
    crlf = {path: text.replace("\n", "\r\n") for path, text in files.items()}
    assert pack_version(files) == pack_version(crlf)
    assert pack_version(files).startswith("pack-")
