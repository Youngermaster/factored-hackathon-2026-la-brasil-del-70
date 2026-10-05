"""The committed model cards validate, cite files that exist, and agree with the defaults the settings serve."""

import re
from pathlib import Path

import pytest

from bank_agent.adapters.evaluation.model_cards import MAX_CARDS_BYTES, FilesystemModelCards
from bank_agent.bootstrap.settings import DEFAULT_MODEL_CARDS_FILE, RetrievalSettings, WorkflowSettings
from bank_agent.domain.errors import ConfigurationError
from bank_agent.domain.intelligence import ModelComponent
from bank_agent.domain.model_inventory import ModelCardSet

REPOSITORY = Path(__file__).resolve().parents[5]


@pytest.fixture
async def committed() -> ModelCardSet:
    return await FilesystemModelCards(DEFAULT_MODEL_CARDS_FILE).read()


async def test_the_committed_cards_validate_and_cover_every_learned_component(committed: ModelCardSet) -> None:
    components = {card.component for card in committed.cards}
    assert components == {
        ModelComponent.ROUTER,
        ModelComponent.RESOLVER,
        ModelComponent.RISK_ESTIMATOR,
        ModelComponent.RETRIEVER,
    }
    assert committed.measurement == "offline"
    assert committed.data == "synthetic"
    assert [promotion.decision for promotion in committed.promotions] == [
        "router_and_resolver_defaults",
        "risk_estimator_default",
    ]
    assert all(promotion.measurement == "simulated" for promotion in committed.promotions)


async def test_every_cited_file_exists(committed: ModelCardSet) -> None:
    paths = {card.source for card in committed.cards} | {card.report for card in committed.cards}
    paths |= {promotion.source for promotion in committed.promotions}
    missing = sorted(path for path in paths if not (REPOSITORY / path).is_file())
    assert not missing


async def test_each_report_was_generated_at_the_commit_the_card_names(committed: ModelCardSet) -> None:
    for card in committed.cards:
        header = (REPOSITORY / card.report).read_text(encoding="utf-8")[:2000]
        assert card.git_sha in header, f"{card.model} names {card.git_sha}, not in {card.report}"


async def test_the_default_cards_name_the_baselines_the_settings_serve(committed: ModelCardSet) -> None:
    workflow = WorkflowSettings(_env_file=None)
    retrieval = RetrievalSettings(_env_file=None)
    defaults = {(card.component, f"{card.model.name}@{card.model.version}") for card in committed.cards
                if card.role == "default"}  # fmt: skip
    assert defaults == {
        (ModelComponent.ROUTER, workflow.router),
        (ModelComponent.RESOLVER, workflow.resolver),
        (ModelComponent.RISK_ESTIMATOR, workflow.risk_estimator),
        (ModelComponent.RETRIEVER, f"{retrieval.retriever}@1"),
    }
    served_rows = [row for promotion in committed.promotions for row in promotion.rows if row.served]
    assert {model for row in served_rows for model in row.models} == {
        f"router:{workflow.router}",
        f"resolver:{workflow.resolver}",
        f"risk_estimator:{workflow.risk_estimator}",
    }


async def test_every_card_metric_appears_in_its_report(committed: ModelCardSet) -> None:
    """A guard against typing a number that the generated report never printed."""
    for card in committed.cards:
        text = (REPOSITORY / card.report).read_text(encoding="utf-8")
        numbers = set(re.findall(r"-?\d+\.\d+", text))
        for metric in card.metrics:
            candidates = {f"{metric.value:.{digits}f}" for digits in (2, 3, 4)}
            assert candidates & numbers, f"{card.model} {metric.name} {metric.value} is not in {card.report}"


async def test_every_promotion_count_appears_in_its_source(committed: ModelCardSet) -> None:
    for promotion in committed.promotions:
        text = (REPOSITORY / promotion.source).read_text(encoding="utf-8")
        for row in promotion.rows:
            counts = (row.safe_automated_resolution, row.unsafe_outcomes, row.routing_correct,
                      row.escalation_unnecessary, row.escalation_missed)  # fmt: skip
            for metric in counts:
                if metric is not None:
                    assert f"{metric.count}/{metric.denominator}" in text, f"{row.models} {metric}"
            assert row.run_id is None or row.run_id in text
            assert row.git_sha is None or row.git_sha in text


async def test_a_missing_file_is_an_empty_set(tmp_path: Path) -> None:
    cards = await FilesystemModelCards(tmp_path / "absent.yaml").read()
    assert (cards.cards, cards.promotions) == ((), ())


@pytest.mark.parametrize(
    "content",
    [
        "cards: [{component: router}]\n",
        "schema_version: '9.9.9'\n",
        "secret-token-value: [\n",
    ],
)
async def test_an_invalid_file_names_the_file_never_its_content(tmp_path: Path, content: str) -> None:
    path = tmp_path / "cards.yaml"
    path.write_text(content, encoding="utf-8")
    with pytest.raises(ConfigurationError) as raised:
        await FilesystemModelCards(path).read()
    assert "cards.yaml" in str(raised.value)
    assert "secret-token-value" not in str(raised.value)


async def test_an_oversized_file_is_refused(tmp_path: Path) -> None:
    path = tmp_path / "cards.yaml"
    path.write_text("#" * (MAX_CARDS_BYTES + 1), encoding="utf-8")
    with pytest.raises(ConfigurationError, match="larger than"):
        await FilesystemModelCards(path).read()
