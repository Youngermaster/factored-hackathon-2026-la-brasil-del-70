"""The real policy pack under ``policies/``: schema, parity, placeholders, versions, bindings, catalog, lexicon."""

import json
from decimal import Decimal
from pathlib import Path

import jsonschema
import pytest
import yaml

from bank_agent.adapters.policy.files import read_pack_files
from bank_agent.adapters.policy.filesystem import FilesystemCreditCatalog, FilesystemPolicyRepository
from bank_agent.bootstrap.settings import DEFAULT_POLICY_DIR
from bank_agent.domain.errors import PolicyPackInvalidError
from bank_agent.domain.locale import Country, Language, Locale
from bank_agent.domain.policy import ClauseFamily
from bank_agent.domain.workflow_catalog import WORKFLOW_CATALOG
from bank_agent.policy.catalog_doc import BODY_START, render_catalog
from bank_agent.policy.explain import render_body
from bank_agent.policy.lexicon import approval_terms
from bank_agent.policy.loader import load_pack
from bank_agent.policy.loader.catalog import check_catalog_against_pack, parse_catalog
from bank_agent.policy.loader.clauses import CLAUSE_PATH
from bank_agent.policy.loader.documents import placeholders

REPOSITORY = DEFAULT_POLICY_DIR.parent
SCHEMA = json.loads((REPOSITORY / "contracts" / "schemas" / "policy_clause.v1.json").read_text(encoding="utf-8"))
FILES = read_pack_files(DEFAULT_POLICY_DIR)
PACK = load_pack(FILES)
CREDIT_FAMILIES = {ClauseFamily.CRE, ClauseFamily.ELG}
SEEDED_CODES = ("MX-PL-STANDARD", "CO-PL-STANDARD", "AR-PL-STANDARD")


def clause_paths() -> list[str]:
    return [path for path in FILES if CLAUSE_PATH.fullmatch(path)]


@pytest.mark.parametrize("path", clause_paths())
def test_every_front_matter_validates_against_the_committed_schema(path: str) -> None:
    front = yaml.safe_load(FILES[path].split("---\n")[1])
    front["effective_from"] = front["effective_from"].isoformat()
    for value in front["params"].values():
        if isinstance(value, dict):
            value["amount"] = str(value["amount"])
    jsonschema.validate(front, SCHEMA)
    assert front["synthetic"] is True


def test_every_clause_has_es_pt_and_en_twins_with_equal_params_and_placeholders() -> None:
    for clause_id in PACK.clause_ids():
        twins = [PACK.get_clause(clause_id, language) for language in Language]
        assert len({twin.metadata.params.__repr__() for twin in twins}) == 1
        assert len({frozenset(placeholders(twin.body)) for twin in twins}) == 1
        assert len({twin.metadata.version for twin in twins}) == 1


def test_only_the_sla_and_auto_limit_clauses_moved_past_version_1() -> None:
    """The SLA clauses gained a sentence (version 2); the auto-limit clauses gained a synthetic USD rate (version 2)."""
    moved = {clause_id: PACK.get_clause(clause_id, Language.ES).metadata.version for clause_id in PACK.clause_ids()}
    assert {clause_id: version for clause_id, version in moved.items() if version != 1} == {
        "DSP-AR-2": 2,
        "DSP-CO-2": 2,
        "DSP-MX-2": 2,
        "DSP-AR-3": 2,
        "DSP-CO-3": 2,
        "DSP-MX-3": 2,
    }


def test_no_placeholder_is_left_unresolved_when_rendered() -> None:
    for clause in PACK.list_clauses():
        for locale in Locale:
            assert "{" not in render_body(clause, locale)


def test_the_version_lock_matches_the_files() -> None:
    lock = yaml.safe_load(FILES["versions.lock.yaml"])["clauses"]
    assert set(lock) == set(PACK.clause_ids())
    assert all(entry["version"] == PACK.get_clause(cid, Language.ES).metadata.version for cid, entry in lock.items())


def test_every_workflow_state_names_at_least_one_clause_beyond_the_common_ones() -> None:
    for descriptor in WORKFLOW_CATALOG.descriptors:
        states = PACK.bindings.workflows[descriptor.id]
        assert descriptor.entry_state in states
        for state, binding in states.items():
            assert binding.clauses, f"{descriptor.id}.{state}"
            for country in Country:
                bound = PACK.get_bound(descriptor.id, state, country, Language.PT)
                assert all(c.metadata.jurisdiction.value in (country.value, "ALL") for c in bound)


def test_country_specific_clauses_exist_for_every_jurisdiction() -> None:
    for template in ("DSP-{c}-1", "DSP-{c}-2", "DSP-{c}-3", "ESC-{c}-2", "CRE-{c}-1", "ELG-{c}-1.1", "ELG-{c}-1.2"):
        for country in Country:
            assert PACK.get_clause(template.format(c=country.value), Language.ES)


def test_no_credit_text_contains_approval_wording() -> None:
    credit = [c for c in PACK.list_clauses() if c.metadata.family in CREDIT_FAMILIES]
    credit += [PACK.get_clause(cid, lang) for cid in ("ESC-ALL-4", "INF-ALL-3") for lang in Language]
    for clause in credit:
        assert approval_terms(f"{clause.metadata.summary} {clause.body}") == (), clause.metadata.clause_id
    for language in Language:
        text = FILES[f"messages/eligibility.{language.value}.yaml"]
        messages = yaml.safe_load(text)
        for group in messages.values():
            for value in group.values():
                assert approval_terms(value) == (), value


def test_every_elg_clause_says_it_is_synthetic_and_decides_nothing() -> None:
    words = {
        Language.ES: ("sintétic", "decisión"),
        Language.PT: ("sintétic", "decisão"),
        Language.EN: ("synthetic", "decision"),
    }
    for clause in PACK.list_clauses():
        if clause.metadata.family is ClauseFamily.ELG:
            body = clause.body.casefold()
            assert all(word in body for word in words[clause.metadata.language])


def test_the_catalog_validates_and_publishes_the_seeded_codes() -> None:
    catalog = FilesystemCreditCatalog.from_directory(DEFAULT_POLICY_DIR, PACK)
    for code in SEEDED_CODES:
        product = catalog.get(code)  # type: ignore[arg-type]
        assert product is not None
        assert product.synthetic is True
        assert catalog.display(product.product_code, Language.PT) is not None
    for country in Country:
        assert len(catalog.list(country)) == 3
    assert catalog.display("XX-NONE", Language.ES) is None  # type: ignore[arg-type]


def test_the_seeded_application_amounts_are_inside_the_product_ranges() -> None:
    from bank_data.seed.bundle import SEEDED_APPLICATION_AMOUNTS, SEEDED_APPLICATION_PRODUCTS

    catalog = FilesystemCreditCatalog.from_directory(DEFAULT_POLICY_DIR, PACK)
    for country, code in SEEDED_APPLICATION_PRODUCTS.items():
        product = catalog.get(code)  # type: ignore[arg-type]
        assert product is not None
        assert product.min_amount.amount <= Decimal(SEEDED_APPLICATION_AMOUNTS[country]) <= product.max_amount.amount


def test_the_repository_adapter_serves_the_pack() -> None:
    repository = FilesystemPolicyRepository.from_directory(DEFAULT_POLICY_DIR)
    assert repository.pack_version() == PACK.version
    assert repository.get_clause("DSP-CO-1", Language.PT).metadata.params["dispute_window_days"] == 60
    assert repository.list_clauses(Language.EN, Country.AR)
    assert [
        c.metadata.clause_id for c in repository.get_bound(WORKFLOW_CATALOG.ids()[2], "START", Country.MX, Language.ES)
    ]


def test_the_catalog_page_is_current() -> None:
    committed = (REPOSITORY / "docs" / "policy" / "catalog.md").read_text(encoding="utf-8")
    entries = parse_catalog(FILES)
    fresh = render_catalog(PACK, entries, generated_at="now", commit="head")
    assert committed[committed.index(BODY_START) :] == fresh[fresh.index(BODY_START) :], "run make policy-catalog"
    assert f"`{PACK.version}`" in committed


def mutated(path: str, old: str, new: str) -> dict[str, str]:
    assert old in FILES[path]
    return {**FILES, path: FILES[path].replace(old, new)}


@pytest.mark.parametrize(
    ("files", "message"),
    [
        (
            mutated("clauses/dsp/DSP-CO-1.pt.md", "dispute_window_days: 60", "dispute_window_days: 61"),
            "differs in params",
        ),
        (mutated("clauses/dsp/DSP-CO-1.es.md", "Colombia puedes", "Colombia siempre puedes"), "without a version bump"),
        (mutated("clauses/dsp/DSP-CO-1.en.md", "{dispute_window_days}", "{window}"), "names no parameter"),
        (mutated("clauses/acc/ACC-ALL-1.es.md", "ACC.as_of_disclosed]", "ACC.nonexistent]"), "unregistered rule"),
        (mutated("matrix.yaml", "credit: [CONFIRM_APPLICATION", "dispute: [CONFIRM_APPLICATION"), "does not own"),
        (mutated("bindings.yaml", "[ACC-ALL-1, ACC-ALL-2, ACC-ALL-3]", "[ACC-ALL-9]"), "unknown clause"),
        (
            mutated("bindings.yaml", "    ANSWER_CASE_STATUS:", "    RETIRED_STATUS:"),
            "no binding for its state ANSWER_CASE_STATUS",
        ),
        (mutated("bindings.yaml", "    ANSWER_CASE_STATUS:", "    RETIRED_STATUS:"), "has no state RETIRED_STATUS"),
        (mutated("clauses/elg/ELG-AR-1.2.es.md", "min_credit_score: 650", "min_credit_score: yes"), "of type int"),
        ({k: v for k, v in FILES.items() if k != "clauses/esc/ESC-AR-2.en.md"}, "no en twin"),
    ],
)
def test_the_loader_rejects_a_broken_pack(files: dict[str, str], message: str) -> None:
    with pytest.raises(PolicyPackInvalidError, match=message):
        load_pack(files)


def test_the_catalog_check_rejects_a_product_with_the_wrong_eligibility_clauses() -> None:
    files = mutated("credit/MX-PL-STANDARD.yaml", "ELG-MX-1.2", "ELG-MX-1.1")
    with pytest.raises(PolicyPackInvalidError, match="MX-PL-STANDARD"):
        check_catalog_against_pack(parse_catalog(files), PACK)


def test_the_policy_commands_write_the_lock_and_the_catalog(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from bank_agent.cli import app

    pack_dir = tmp_path / "policies"
    for path, text in FILES.items():
        (pack_dir / path).parent.mkdir(parents=True, exist_ok=True)
        (pack_dir / path).write_text(text, encoding="utf-8")
    runner = CliRunner()
    assert runner.invoke(app, ["policy", "lock", "--policy-dir", str(pack_dir)]).exit_code == 0
    page = tmp_path / "catalog.md"
    result = runner.invoke(app, ["policy", "catalog", "--policy-dir", str(pack_dir), "--output", str(page)])
    assert result.exit_code == 0
    assert page.read_text(encoding="utf-8").startswith("# Policy catalog")
    changed = pack_dir / "clauses" / "dsp" / "DSP-CO-1.es.md"
    changed.write_text(changed.read_text(encoding="utf-8").replace("puedes", "podrás"), encoding="utf-8")
    refused = runner.invoke(app, ["policy", "lock", "--policy-dir", str(pack_dir)])
    assert refused.exit_code == 2
    broken = runner.invoke(app, ["policy", "catalog", "--policy-dir", str(pack_dir), "--output", str(page)])
    assert broken.exit_code == 2
