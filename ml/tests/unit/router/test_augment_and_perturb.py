"""Augmentation and perturbation functions: determinism, provenance, and what each one changes."""

from pathlib import Path

import pytest
import yaml

from bank_agent.domain.workflow import Intent
from bank_ml.common.seeds import rng
from bank_ml.router.augment import augment, fill, slang
from bank_ml.router.corpus import CorpusError, Seed, load_lexicon, load_seeds
from bank_ml.router.perturb import (
    add_fillers,
    casing,
    drop_accents,
    replace_words,
    speech_to_text,
    strip_punctuation,
    truncate,
    typo,
)

LEXICON = load_lexicon()
SEED = Seed("dispute_new:es-MX:99", Intent.DISPUTE_NEW, "es-MX", "No reconozco un cargo de {amount} en {merchant}")


def test_fill_uses_the_first_values_for_the_canonical_text() -> None:
    assert fill(SEED, LEXICON, None) == "No reconozco un cargo de 500 pesos en Super Ahorro"
    drawn = fill(SEED, LEXICON, rng("test", 1))
    assert "{" not in drawn
    assert drawn != fill(SEED, LEXICON, None)


def test_augment_is_deterministic_and_labels_provenance() -> None:
    items = augment(SEED, LEXICON)
    assert items == augment(SEED, LEXICON)
    assert items[0].augmentation == "canonical"
    assert items[0].provenance == "team_authored"
    assert {item.augmentation for item in items} >= {"canonical", "slots", "typo", "casing"}
    assert all(item.provenance == "augmented_from:dispute_new:es-MX:99" for item in items[1:])
    assert len({item.text for item in items}) == len(items)
    assert all(item.intent is Intent.DISPUTE_NEW and item.language == "es" for item in items)


def test_slang_and_accents_apply_only_when_they_change_the_text() -> None:
    generator = rng("test", 0)
    assert slang("Necesito el dinero ahora por favor", "es-MX", LEXICON, generator) is not None
    assert slang("hola", "es-MX", LEXICON, generator) is None
    plain = Seed("greeting_or_other:es-CO:99", Intent.GREETING_OR_OTHER, "es-CO", "hola buenas")
    kinds = {item.augmentation for item in augment(plain, LEXICON)}
    assert "accents" not in kinds
    assert "slots" not in kinds


def test_typing_perturbations() -> None:
    assert typo("hola", rng("test", 3), LEXICON.keyboard) != "hola"
    assert typo("123", rng("test", 3), LEXICON.keyboard) == "123"
    assert casing("¿Mi Saldo?", rng("test", 0)) in {"¿mi saldo?", "¿MI SALDO?", "mi saldo"}
    assert drop_accents("Cartão bloqueado, ¿también?") == "Cartao bloqueado, ¿tambien?"
    assert strip_punctuation("¡Hola! ¿Qué tal?") == "Hola Qué tal"


def test_speech_to_text_perturbations() -> None:
    assert replace_words("Ya hice el pago", {"hice": "ise", "ya": "lla"}) == "lla ise el pago"
    assert truncate("uno dos tres cuatro cinco") == "uno dos tres"
    assert truncate("uno") == "uno"
    assert len(add_fillers("quiero mi saldo", ["este"], rng("test", 0), count=2).split()) == 5
    rendered = speech_to_text("Ya hice el pago, ¿llegó?", LEXICON.homophones["es"], ["eh"], rng("test", 0))
    assert rendered == rendered.lower()
    assert "ise" in rendered
    assert "yego" in rendered
    assert "?" not in rendered


def test_the_loader_refuses_malformed_corpora(tmp_path: Path) -> None:
    seeds = tmp_path / "seeds"
    seeds.mkdir()
    (seeds / "card_block.yaml").write_text(yaml.safe_dump({"intent": "card_block", "seeds": {"es-MX": ["x"]}}))
    with pytest.raises(CorpusError, match="locales"):
        load_seeds(tmp_path)
    (seeds / "card_block.yaml").write_text(yaml.safe_dump({"intent": "nope"}))
    with pytest.raises(CorpusError, match="unknown intent"):
        load_seeds(tmp_path)
    locales = {"es-MX": ["{bogus} x"], "es-CO": ["x"], "es-AR": ["x"], "pt-BR": ["x"]}
    (seeds / "card_block.yaml").write_text(yaml.safe_dump({"intent": "card_block", "seeds": locales}))
    with pytest.raises(CorpusError, match="unknown slots"):
        load_seeds(tmp_path)
    (seeds / "card_block.yaml").write_text(yaml.safe_dump({"intent": "card_status", "seeds": locales}))
    with pytest.raises(CorpusError, match="file name"):
        load_seeds(tmp_path)
    (seeds / "card_block.yaml").write_text(yaml.safe_dump({"intent": "card_block", "seeds": {**locales, "es-MX": [1]}}))
    with pytest.raises(CorpusError, match="string or a mapping"):
        load_seeds(tmp_path)
    (seeds / "card_block.yaml").write_text(
        yaml.safe_dump({"intent": "card_block", "seeds": {**locales, "es-MX": ["x"]}})
    )
    with pytest.raises(CorpusError, match="no seeds for intents"):
        load_seeds(tmp_path)
    scoped = {**locales, "es-MX": [{"text": "x", "scope": "off_domain"}]}
    (seeds / "card_block.yaml").write_text(yaml.safe_dump({"intent": "card_block", "seeds": scoped}))
    with pytest.raises(CorpusError, match="scope"):
        load_seeds(tmp_path)


def test_the_lexicon_needs_every_slot_for_every_locale(tmp_path: Path) -> None:
    document = yaml.safe_load((Path(__file__).parents[3] / "corpus" / "router" / "lexicon.yaml").read_text())
    del document["slots"]["amount"]["pt-BR"]
    (tmp_path / "lexicon.yaml").write_text(yaml.safe_dump(document, allow_unicode=True))
    with pytest.raises(CorpusError, match="amount"):
        load_lexicon(tmp_path)
