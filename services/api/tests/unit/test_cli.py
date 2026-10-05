import pytest
from typer.testing import CliRunner

from bank_agent import __version__
from bank_agent.adapters.vector import qdrant as qdrant_module
from bank_agent.adapters.vector.memory import InMemoryVectorStore
from bank_agent.bootstrap import embeddings as embeddings_module
from bank_agent.cli import app
from bank_agent_retrieval import HashingEmbedder

runner = CliRunner()


def test_help_lists_the_version_command() -> None:
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    assert "version" in result.output


def test_no_arguments_shows_help() -> None:
    result = runner.invoke(app, [])

    assert "Usage" in result.output


def test_version_prints_distribution_name_and_version() -> None:
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.output.strip() == f"bank-agent {__version__}"


def test_db_upgrade_needs_the_owner_password() -> None:
    result = runner.invoke(app, ["db", "upgrade"])

    assert result.exit_code == 2
    assert "POSTGRES_ADMIN_PASSWORD is not set" in result.output


def test_index_qdrant_needs_a_store_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RETRIEVAL_QDRANT_URL", raising=False)
    result = runner.invoke(app, ["index", "qdrant"])

    assert result.exit_code == 2
    assert "no vector store URL" in result.output


def test_index_qdrant_is_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    store = InMemoryVectorStore()
    monkeypatch.setattr(qdrant_module, "QdrantVectorStore", lambda url, **_: store)
    monkeypatch.setattr(embeddings_module, "build_hosted_embedder", lambda *_, **__: HashingEmbedder())

    first = runner.invoke(app, ["index", "qdrant", "--url", "http://qdrant:6333"])
    second = runner.invoke(app, ["index", "qdrant", "--url", "http://qdrant:6333", "--recreate"])

    assert first.exit_code == 0, first.output
    assert first.output.startswith("created policy-clauses-pack-")
    assert "123 points, model fixture/hashing|q|p" in first.output
    assert second.exit_code == 0, second.output
    assert second.output.splitlines()[0].startswith("dropped policy-clauses-pack-")
    assert len(store.list_collections()) == 1
