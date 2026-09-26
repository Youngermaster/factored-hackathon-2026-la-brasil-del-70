"""A scripted language detector."""

from collections.abc import Mapping

from bank_agent.domain.base import UntrustedText
from bank_agent.domain.intelligence import LanguageDetection, LanguageScore, ModelComponent, ModelRef
from bank_agent.domain.locale import Language

FAKE_DETECTOR = ModelRef(component=ModelComponent.LANGUAGE_DETECTOR, name="fake", version="1")


class FakeLanguageDetector:
    """Implements the ``LanguageDetector`` port: a default detection, plus exact-text overrides."""

    def __init__(
        self,
        default: Language | None = Language.ES,
        *,
        confidence: float = 0.99,
        overrides: Mapping[str, LanguageDetection] | None = None,
    ) -> None:
        self._default = default
        self._confidence = confidence
        self._overrides = dict(overrides or {})

    def set(self, text: str, language: Language | None, *, confidence: float = 0.99, is_mixed: bool = False) -> None:
        """Script the detection for one exact text."""
        candidates = (LanguageScore(language=language, score=confidence),) if language is not None else ()
        self._overrides[text] = LanguageDetection(
            language=language, confidence=confidence, candidates=candidates, is_mixed=is_mixed, detector=FAKE_DETECTOR
        )

    def detect(self, text: UntrustedText) -> LanguageDetection:
        scripted = self._overrides.get(text)
        if scripted is not None:
            return scripted
        candidates = (LanguageScore(language=self._default, score=self._confidence),) if self._default else ()
        return LanguageDetection(
            language=self._default, confidence=self._confidence, candidates=candidates, detector=FAKE_DETECTOR
        )
