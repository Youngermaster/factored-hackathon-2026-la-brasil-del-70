"""The B0 menu router: fixed menu words first, then the keyword router. It implements ``IntentRouter``."""

import re

from bank_agent.application.understanding.text import fold
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.intelligence import IntentPrediction, IntentScore, ModelComponent, ModelRef
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent
from bank_agent.ports.models import IntentRouter

MENU_ROUTER = ModelRef(component=ModelComponent.ROUTER, name="menu", version="1")
_MENU: tuple[tuple[Intent, str], ...] = (
    (Intent.DISPUTE_STATUS, r"^estado de (una |mi )?reclamacion"),
    (Intent.DISPUTE_NEW, r"^reclamar"),
    (Intent.CARD_STATUS, r"^estado de (mi )?tarjeta"),
    (Intent.CARD_BLOCK, r"^bloquear"),
    (Intent.HUMAN_REQUEST, r"^hablar con una persona"),
)


class MenuRouter:
    def __init__(self, fallback: IntentRouter) -> None:
        self._fallback = fallback

    def route(self, text: UntrustedText, language: Language) -> IntentPrediction:
        folded = fold(text)
        for intent, pattern in _MENU:
            if re.search(pattern, folded):
                return IntentPrediction(
                    intent=intent,
                    confidence=0.99,
                    candidates=(IntentScore(intent=intent, score=0.99),),
                    below_threshold=False,
                    model=MENU_ROUTER,
                )
        return self._fallback.route(text, language)
