"""The corpus from a pack, and building, writing, and loading indexes keyed by the pack version."""

import json
from pathlib import Path

import pytest

from bank_agent.adapters.retrieval import index_store
from bank_agent.adapters.retrieval.corpus import build_corpus, corpus_digest, document_locale
from bank_agent.adapters.retrieval.index_store import build_index, load_index, write_index
from bank_agent.domain.errors import RetrievalIndexError
from bank_agent.domain.locale import Country, Language, Locale
from bank_agent.domain.policy import ClauseFamily, Jurisdiction
from bank_agent_policy import fixture_pack
from bank_agent_retrieval import HashingEmbedder, document


def test_the_corpus_has_every_current_clause_but_eligibility_rules() -> None:
    pack = fixture_pack()
    documents = build_corpus(pack)
    assert ClauseFamily.ELG not in {d.family for d in documents}
    assert "ELG-ALL-1" in pack.clause_ids()
    expected = {c.metadata.clause_id for c in pack.list_clauses() if c.metadata.family is not ClauseFamily.ELG}
    assert {d.clause_id for d in documents} == expected
    assert {d.language for d in documents} == set(Language)
    assert [d.key for d in documents] == sorted(d.key for d in documents)
    first = documents[0]
    assert first.text.startswith(pack.get_clause(first.clause_id, first.language).metadata.summary)


def test_documents_are_visible_only_in_their_language_and_jurisdiction() -> None:
    mexico = document("DSP-MX-1", "plazo")
    common = document("CRD-ALL-2", "bloqueo")
    assert mexico.visible_to(Language.ES, Country.MX)
    assert not mexico.visible_to(Language.ES, Country.CO)
    assert not mexico.visible_to(Language.PT, Country.MX)
    assert common.visible_to(Language.ES, Country.AR)
    assert mexico.key == "DSP-MX-1@1:es"


def test_bodies_render_in_the_locale_of_their_language_and_jurisdiction() -> None:
    assert document_locale(Language.ES, Jurisdiction.CO) is Locale.ES_CO
    assert document_locale(Language.ES, Jurisdiction.ALL) is Locale.ES_MX
    assert document_locale(Language.PT, Jurisdiction.AR) is Locale.PT_BR
    assert document_locale(Language.EN, Jurisdiction.MX) is Locale.EN_US


def test_the_digest_depends_on_text_not_order() -> None:
    one, two = document("DSP-MX-1", "plazo"), document("CRD-ALL-2", "bloqueo")
    assert corpus_digest([one, two]) == corpus_digest([two, one])
    assert corpus_digest([one]) != corpus_digest([document("DSP-MX-1", "otro plazo")])


def test_an_index_round_trips_through_its_pack_version_directory(tmp_path: Path) -> None:
    pack = fixture_pack()
    embedder = HashingEmbedder()
    built = build_index(pack, embedder=embedder)
    directory = write_index(built, tmp_path)
    assert directory == tmp_path / pack.pack_version()
    assert json.loads((directory / "manifest.json").read_text(encoding="utf-8"))["embedding_model"] == embedder.model_id
    loaded = load_index(tmp_path, pack, embedding_model=embedder.model_id)
    assert loaded.manifest == built.manifest
    assert loaded.dense is not None
    assert built.dense is not None
    assert loaded.dense.vectors == built.dense.vectors
    assert load_index(tmp_path, pack).dense is None


def test_rewriting_without_an_embedder_removes_stale_vectors(tmp_path: Path) -> None:
    pack = fixture_pack()
    write_index(build_index(pack, embedder=HashingEmbedder()), tmp_path)
    directory = write_index(build_index(pack), tmp_path)
    assert not (directory / "dense.json").exists()
    with pytest.raises(RetrievalIndexError, match="no dense vectors"):
        load_index(tmp_path, pack, embedding_model=HashingEmbedder().model_id)


def test_loading_refuses_a_missing_index_and_names_what_exists(tmp_path: Path) -> None:
    write_index(build_index(fixture_pack("pack-fixture-0001")), tmp_path)
    with pytest.raises(RetrievalIndexError, match=r"pack version pack-fixture-0002 \(found: pack-fixture-0001\)"):
        load_index(tmp_path, fixture_pack("pack-fixture-0002"))
    with pytest.raises(RetrievalIndexError, match="found: none"):
        load_index(tmp_path / "absent", fixture_pack())


def _rewrite_manifest(directory: Path, **changes: object) -> None:
    path = directory / "manifest.json"
    manifest = json.loads(path.read_text(encoding="utf-8"))
    manifest.update(changes)
    path.write_text(json.dumps(manifest), encoding="utf-8")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"pack_version": "pack-other"}, "built for pack version pack-other"),
        ({"tokenizer": "fold@0"}, "uses tokenizer fold@0"),
        ({"corpus_digest": "0" * 64}, "another corpus"),
        ({"document_count": 1}, "another corpus"),
        ({"format": 9}, "malformed"),
    ],
)
def test_loading_refuses_a_mismatched_manifest(tmp_path: Path, changes: dict[str, object], message: str) -> None:
    pack = fixture_pack()
    directory = write_index(build_index(pack), tmp_path)
    _rewrite_manifest(directory, **changes)
    with pytest.raises(RetrievalIndexError, match=message):
        load_index(tmp_path, pack)


def test_loading_refuses_unreadable_or_foreign_files(tmp_path: Path) -> None:
    pack = fixture_pack()
    embedder = HashingEmbedder()
    directory = write_index(build_index(pack, embedder=embedder), tmp_path)
    dense = json.loads((directory / "dense.json").read_text(encoding="utf-8"))
    dense["documents"] = dense["documents"][:-1]
    (directory / "dense.json").write_text(json.dumps(dense), encoding="utf-8")
    with pytest.raises(RetrievalIndexError, match="dense index was built for another corpus"):
        load_index(tmp_path, pack, embedding_model=embedder.model_id)
    (directory / index_store.BM25_FILE).write_text("{not json", encoding="utf-8")
    with pytest.raises(RetrievalIndexError, match=r"cannot read bm25\.json"):
        load_index(tmp_path, pack)
