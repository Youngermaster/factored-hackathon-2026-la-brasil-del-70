"""``language_detector:lexical@1``: a deterministic detector for Spanish, Portuguese, and English.

It counts marker words that belong to one language only (``nao``, ``voce``, ``cartao`` for Portuguese; ``tarjeta``,
``quiero``, ``usted`` for Spanish; ``the``, ``my``, ``please`` for English) and orthographic markers (``ã``, ``õ``,
``ç``, ``lh``, ``nh`` for Portuguese; ``ñ``, ``¿``, ``¡`` for Spanish) before folding. The language with most
markers wins when it has at least ``MIN_MARKERS`` and leads the runner-up by ``MARGIN`` of all markers; otherwise
the result is uncertain (``language is None``) and the engine asks the customer. Words that a language shares
with another after accent folding (``por``, ``favor``, ``mas``/``más``) are not markers: a production QA pass
(2026-10-05) saw "Por que precisa de análise?" switch a Portuguese conversation to Spanish and "la más reciente"
switch a Spanish one to Portuguese. Input with two languages each
holding ``MIXED_SHARE`` of the markers is marked mixed and answered in the dominant one.

The prompt names a lingua-language-detector adapter; its 2.2.0 wheels are about 170 MB, above the 50 MB rule,
so it waits for the team's approval (``docs/BACKLOG.md``). This detector serves behind the same port until then.
"""

import re

from bank_agent.application.understanding.text import words
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.intelligence import LanguageDetection, LanguageScore, ModelComponent, ModelRef
from bank_agent.domain.locale import Language

LEXICAL_DETECTOR = ModelRef(component=ModelComponent.LANGUAGE_DETECTOR, name="lexical", version="1")
MIN_MARKERS = 1.0
MARGIN = 0.34
MIXED_SHARE = 0.25

_SPANISH = """
        el los las del una unos yo usted ustedes vos mi mis tu tus quiero quisiera tengo tarjeta tarjetas cargo
        cargos compra cuenta ayer anteayer antier hoy semana pasado pasada mes reconozco desconozco cobraron hola
        gracias necesito puedo tambien pero hace dias cuando donde esta estoy fue esa ese eso esto aqui
        si bloquear bloquea bloqueala perdi robaron reclamo reclamacion monto dinero lucas luca palos varos nueva
        che sos tenes queres podes decime mande ahorita voy ahora muy hay
        un en lo recibi compre prestamo prestamos califico solicitud plazo
        """
_PORTUGUESE = """
        nao voce voces eu meu minha meus minhas cartao cartoes conta compra ontem anteontem hoje semana passada
        passado mes reconheco desconheco cobraram ola oi obrigado obrigada preciso posso tambem faz dias
        quando onde esta estou foi essa esse isso isto aqui sim bloquear bloqueia perdi roubaram contestacao valor
        dinheiro novo nova um uma com pelo pela ao dos das estao tenho quero queria gostaria cobranca reais
        qual quais precisa pendente vai sao em agora os do
        """
_ENGLISH = """
        the my your you i and is are was not do did does please card charge account yesterday today week last
        month want would like need can could hello hi thanks thank what how why when where this that it block
        lost stolen new dispute help with have has
        """
_MARKERS: dict[Language, frozenset[str]] = {
    Language.ES: frozenset(_SPANISH.split()),
    Language.PT: frozenset(_PORTUGUESE.split()),
    Language.EN: frozenset(_ENGLISH.split()),
}
_ORTHOGRAPHY: dict[Language, re.Pattern[str]] = {
    Language.PT: re.compile(r"[ãõç]|lh|nh(?!o\b)", re.IGNORECASE),
    Language.ES: re.compile(r"[ñ¿¡]", re.IGNORECASE),
}


def marker_counts(text: str) -> dict[Language, float]:
    """Marker counts per language: whole marker words, plus half a point per orthographic marker."""
    tokens = words(text)
    counts = {language: float(sum(token in markers for token in tokens)) for language, markers in _MARKERS.items()}
    for language, pattern in _ORTHOGRAPHY.items():
        counts[language] += 0.5 * len(pattern.findall(text))
    exclusive = {language: counts[language] for language in counts}
    for token in tokens:
        owners = [language for language, markers in _MARKERS.items() if token in markers]
        if len(owners) > 1:
            for language in owners:
                exclusive[language] -= 1.0
    return {language: max(value, 0.0) for language, value in exclusive.items()}


class LexicalLanguageDetector:
    """Implements ``LanguageDetector``."""

    model = LEXICAL_DETECTOR

    def detect(self, text: UntrustedText) -> LanguageDetection:
        counts = marker_counts(text)
        total = sum(counts.values())
        ranked = sorted(counts.items(), key=lambda item: (-item[1], list(Language).index(item[0])))
        candidates = tuple(
            LanguageScore(language=language, score=round(value / total, 4))
            for language, value in ranked
            if total > 0 and value > 0
        )
        if total < MIN_MARKERS:
            return LanguageDetection(language=None, confidence=0.0, detector=LEXICAL_DETECTOR)
        (top, top_value), (_, second_value) = ranked[0], ranked[1]
        confidence = round(top_value / total, 4)
        mixed = second_value >= 1.0 and second_value / total >= MIXED_SHARE
        certain = (top_value - second_value) / total >= MARGIN or (mixed and top_value > second_value)
        return LanguageDetection(
            language=top if certain else None,
            confidence=confidence,
            candidates=candidates,
            is_mixed=mixed,
            detector=LEXICAL_DETECTOR,
        )
