"""Robustness and transfer: speech-to-text perturbations of the canonical test seeds, dialect slices, the
Spanish-to-Portuguese transfer gap, held-out dialects (out of distribution), and the language detector.

Every perturbed item keeps its seed's group and label and is marked ``augmented_from:<seed_id>`` with the
perturbation as its augmentation kind (``review_status`` pending, like all generated text). The paraphrase set needs a
language model provider and is reported as pending.
"""

from collections.abc import Callable, Sequence
from dataclasses import replace
from typing import Any

import numpy as np

from bank_agent.adapters.models.lexical_language import LexicalLanguageDetector
from bank_agent.adapters.models.tfidf_router import TfidfIntentRouter, TfidfRouterArtifact
from bank_agent.domain.base import UntrustedText
from bank_ml.common.seeds import rng
from bank_ml.router.augment import Item
from bank_ml.router.corpus import LOCALES, Lexicon
from bank_ml.router.evaluate import Scored, interval
from bank_ml.router.models import UNFITTED, Predictions, RoutePredictor, RouterModel, fit_tfidf
from bank_ml.router.perturb import add_fillers, drop_accents, replace_words, speech_to_text, truncate

STT_KINDS = ("accents", "homophones", "fillers", "truncation", "combined")


def _perturb(item: Item, kind: str, lexicon: Lexicon) -> str:
    generator = rng("stt", kind, item.item_id)
    homophones = lexicon.homophones[item.language]
    fillers = lexicon.fillers[item.locale]
    if kind == "accents":
        return drop_accents(item.text)
    if kind == "homophones":
        return replace_words(item.text, homophones)
    if kind == "fillers":
        return add_fillers(item.text, fillers, generator)
    if kind == "truncation":
        return truncate(item.text)
    return speech_to_text(item.text, homophones, fillers, generator)


def stt_sets(test: Sequence[Item], lexicon: Lexicon) -> dict[str, list[Item]]:
    canonical = [item for item in test if item.augmentation == "canonical"]
    return {
        kind: [
            replace(
                item,
                item_id=f"{item.item_id}~{kind}",
                text=_perturb(item, kind, lexicon),
                provenance=f"augmented_from:{item.seed_id}",
                augmentation=f"stt_{kind}",
            )
            for item in canonical
        ]
        for kind in STT_KINDS
    }


def robustness(models: Sequence[RouterModel], test: Sequence[Item], lexicon: Lexicon) -> dict[str, Any]:
    sets = {"clean": [item for item in test if item.augmentation == "canonical"], **stt_sets(test, lexicon)}
    result: dict[str, Any] = {}
    for model in models:
        result[model.name] = {
            kind: interval(Scored(f"{model.name}:{kind}", items, model.predict(items)).accuracy())
            for kind, items in sets.items()
        }
    result["items_per_set"] = len(sets["clean"])
    return result


def _tfidf_predictor(name: str, train: Sequence[Item], dev: Sequence[Item], c: float) -> RoutePredictor:
    fitted = fit_tfidf(train, dev, c=c)
    return RoutePredictor(name, TfidfIntentRouter(TfidfRouterArtifact.model_validate(fitted.artifact), UNFITTED))


def _accuracy(model: RouterModel, items: Sequence[Item]) -> dict[str, float]:
    predictions: Predictions = model.predict(items)
    return interval(Scored(model.name, items, predictions).accuracy())


def _in_locale(locale: str) -> Callable[[Item], bool]:
    return lambda item: item.locale == locale


def transfer(
    reference: RouterModel, train: Sequence[Item], dev: Sequence[Item], test: Sequence[Item], c: float
) -> dict[str, Any]:
    """TF-IDF retrained without a language or a dialect, against the reference model on the held-out part."""

    def without(predicate: Callable[[Item], bool]) -> tuple[list[Item], list[Item]]:
        return [i for i in train if not predicate(i)], [i for i in dev if not predicate(i)]

    portuguese = [item for item in test if item.language == "pt"]
    es_train, es_dev = without(lambda item: item.language == "pt")
    result: dict[str, Any] = {
        "es_to_pt": {
            "in_language": _accuracy(reference, portuguese),
            "spanish_only": _accuracy(_tfidf_predictor("tfidf:es_only", es_train, es_dev, c), portuguese),
            "items": len(portuguese),
        },
        "held_out_dialect": {},
    }
    for locale in (locale for locale in LOCALES if locale.startswith("es")):
        held = [item for item in test if item.locale == locale]
        sub_train, sub_dev = without(_in_locale(locale))
        result["held_out_dialect"][locale] = {
            "in_distribution": _accuracy(reference, held),
            "held_out": _accuracy(_tfidf_predictor(f"tfidf:without_{locale}", sub_train, sub_dev, c), held),
            "items": len(held),
        }
    return result


def language_detection(items: Sequence[Item]) -> dict[str, Any]:
    """``language_detector:lexical@1`` on the corpus, which carries language labels (BACKLOG: lingua decision)."""
    detector = LexicalLanguageDetector()
    rows: dict[str, Any] = {}
    for language in ("es", "pt"):
        subset = [item for item in items if item.language == language]
        detected = [detector.detect(UntrustedText(item.text)).language for item in subset]
        values = [value.value if value is not None else None for value in detected]
        rows[language] = {
            "items": len(subset),
            "correct": float(np.mean([value == language for value in values])),
            "uncertain": float(np.mean([value is None for value in values])),
            "wrong": float(np.mean([value not in (None, language) for value in values])),
        }
    rows["detector"] = str(detector.detect(UntrustedText("hola")).detector)
    return rows
