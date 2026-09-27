"""The container's grounding services over the real pack, and ``bank-agent index build``."""

import json
import sys
from pathlib import Path

import pytest
from typer.testing import CliRunner

from bank_agent.adapters.retrieval.bm25 import Bm25Retriever
from bank_agent.adapters.retrieval.dense import DenseRetriever
from bank_agent.adapters.retrieval.hybrid import HybridRetriever
from bank_agent.application.grounding.retrieval import RetrievalDecision
from bank_agent.bootstrap.container import Container
from bank_agent.bootstrap.settings import AppSettings, RetrievalSettings, load_settings
from bank_agent.cli import app
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.errors import EmbeddingBackendUnavailableError, RetrievalIndexError
from bank_agent.domain.locale import Country, Language
from bank_agent.domain.workflow import Intent, WorkflowId
from bank_agent_builders import customer
from bank_agent_retrieval import HashingEmbedder


def settings(**retrieval: object) -> AppSettings:
    base = load_settings(env_file=None)
    base.retrieval = RetrievalSettings.model_validate(retrieval)
    return base


def test_the_default_container_answers_informational_questions_with_bm25() -> None:
    grounding = Container(settings()).grounding
    assert isinstance(grounding.retriever, Bm25Retriever)
    outcome = grounding.informational.search(
        intent=Intent.INFORMATIONAL,
        text=UntrustedText("¿Cuántos días tengo para aclarar un cargo que no reconozco?"),
        customer=customer(country=Country.MX),
        language=Language.ES,
    )
    assert outcome.decision is RetrievalDecision.ANSWER
    assert "DSP-MX-1" in [ref.clause_id for ref in outcome.citations]
    assert all(ref.clause_id.split("-")[1] in {"MX", "ALL"} for ref in outcome.citations)
    bound = grounding.bound.for_state(WorkflowId.CREDIT, "START", customer(), Language.PT)
    assert bound.pack_version == grounding.index.manifest.pack_version


@pytest.mark.parametrize(("name", "kind"), [("dense", DenseRetriever), ("hybrid", HybridRetriever)])
def test_dense_and_hybrid_use_an_injected_embedder(name: str, kind: type) -> None:
    grounding = Container(settings(retriever=name), embedder=HashingEmbedder()).grounding
    assert isinstance(grounding.retriever, kind)
    assert grounding.index.dense is not None


def test_dense_without_the_ml_extra_is_a_startup_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setitem(sys.modules, "sentence_transformers", None)
    with pytest.raises(EmbeddingBackendUnavailableError):
        Container(settings(retriever="dense", model_cache_dir=tmp_path))


def test_the_cli_builds_an_index_the_container_loads_and_a_mismatch_is_refused(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["index", "build", "--output", str(tmp_path)])
    assert result.exit_code == 0, result.output
    grounding = Container(settings(index_source="stored", index_dir=tmp_path)).grounding
    directory = tmp_path / grounding.index.manifest.pack_version
    assert (directory / "bm25.json").is_file()
    assert not (directory / "dense.json").exists()
    manifest = json.loads((directory / "manifest.json").read_text(encoding="utf-8"))
    manifest["corpus_digest"] = "0" * 64
    (directory / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(RetrievalIndexError, match="another corpus"):
        Container(settings(index_source="stored", index_dir=tmp_path))
    with pytest.raises(RetrievalIndexError, match="no retrieval index"):
        Container(settings(index_source="stored", index_dir=tmp_path / "empty"))


def test_the_cli_reports_a_broken_pack(tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["index", "build", "--policy-dir", str(tmp_path), "--output", str(tmp_path)])
    assert result.exit_code == 2
