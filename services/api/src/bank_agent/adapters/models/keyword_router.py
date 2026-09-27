"""``router:keyword@1``: a transparent keyword baseline for the ``IntentRouter`` port (Spanish, Portuguese, English).

Each intent has weighted patterns over folded text (accents removed, lower case). An intent's score is its best
pattern weight, raised by 0.05 for every further matching pattern (at most 0.99). The prediction is the best
intent; ``below_threshold`` is true under ``THRESHOLD``. A message that matches nothing is ``greeting_or_other``
at 0.2, so the engine asks what the customer needs. Phase 10 replaces this with a learned router behind the port.
"""

import re
from collections.abc import Mapping

from bank_agent.application.understanding.text import fold
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.intelligence import IntentPrediction, IntentScore, ModelComponent, ModelRef
from bank_agent.domain.locale import Language
from bank_agent.domain.workflow import Intent

KEYWORD_ROUTER = ModelRef(component=ModelComponent.ROUTER, name="keyword", version="1")
THRESHOLD = 0.6
UNMATCHED_CONFIDENCE = 0.2
MAX_CANDIDATES = 5
_STRONG, _MEDIUM, _WEAK = 0.9, 0.7, 0.5

Rule = tuple[str, float]

RULES: Mapping[Intent, tuple[Rule, ...]] = {
    Intent.DISPUTE_NEW: (
        (r"no (la |lo )?reconozco|desconozco|no fui yo|no lo hice|no hice (esa|esta|la) compra", _STRONG),
        (r"nao (a |o )?reconheco|nao fui eu|nao fiz (essa|esta) compra|desconheco", _STRONG),
        (r"(cobro|cargo|cobranca) (indebido|indevida|doble|duplicad[oa]|desconocido|que no)", _STRONG),
        (r"me cobraron (dos veces|de mas|mal)|cobraram (duas vezes|a mais)", _STRONG),
        (r"no (me )?(llego|recibi)|nao (me )?(chegou|recebi)", _MEDIUM),
        (r"cajero .*no (me )?(dio|entrego)|caixa eletronico .*nao", _MEDIUM),
        (r"suscripcion .*cancel|assinatura .*cancel", _MEDIUM),
        (r"reclam(ar|o|acion)|aclaracion|desconocimiento|contest(ar|acao)|disputa", _WEAK),
        (r"i did not make|unrecognized charge|dispute (a|this) charge", _STRONG),
    ),
    Intent.DISPUTE_STATUS: (
        (r"(estado|estatus|seguimiento) de (mi|la|mis|el) (reclam|aclarac|caso|disputa|desconoc)", _STRONG),
        (r"como va (mi|el|la) (reclam|caso|aclarac)|numero de caso", _STRONG),
        (r"(situacao|status|andamento) d[ao] (minha |meu )?(contestacao|caso|reclamacao)", _STRONG),
        (r"status of my (dispute|case)", _STRONG),
    ),
    Intent.CARD_BLOCK: (
        (r"(?<!des)bloque(ar|a|en|ame|o)|(?<!des)bloquei[ao]|congel(ar|a)", _STRONG),
        (r"perdi (mi|la|meu|o)? ?(tarjeta|cartao)|extravi|me (la )?robaron|roubaram|robo de|roubo", _MEDIUM),
        (r"block (my|the) card|lost my card|stolen", _STRONG),
    ),
    Intent.CARD_UNBLOCK_REQUEST: (
        (r"desbloque|desbloquei|reactiv|reativ|volver a activar|ativar de novo", 0.95),
        (r"unblock", 0.95),
    ),
    Intent.CARD_REPLACEMENT_REQUEST: (
        (r"reposicion|reponer|reemplaz|reposicao|segunda via|substitu", 0.93),
        (r"(tarjeta|plastico) nuev|nueva tarjeta|otra tarjeta|(novo|outro) cartao|cartao novo", 0.93),
        (r"(quiero|necesito|pido) (una|otra) nueva|(quero|preciso)( de)? (um|uma|outro|outra) (novo|nova)", 0.93),
        (r"replacement card|new card", 0.93),
    ),
    Intent.CARD_STATUS: (
        (r"estado de (mi|la|las|mis) tarjeta|vencimiento|cuando vence", _STRONG),
        (r"(situacao|status) do (meu )?cartao|validade do cartao|quando vence", _STRONG),
        (r"(mi tarjeta|meu cartao) (no |nao )?(esta|funciona|sirve|passa|pasa)", _STRONG),
        (r"rechaz|recusad|declin", _MEDIUM),
        (r"card status|my card (is|works)", _STRONG),
    ),
    Intent.HUMAN_REQUEST: (
        (r"hablar con (una persona|un humano|un asesor|alguien|un agente|un ejecutivo)|asesor humano", 0.95),
        (r"falar com (uma pessoa|um atendente|um humano|alguem)|atendente humano", 0.95),
        (r"talk to (a person|a human|an agent)", 0.95),
    ),
    Intent.INFORMATIONAL: (
        (r"cuanto tiempo|cuantos dias|que plazo|como funciona|que pasa si|cual es el plazo", _MEDIUM),
        (r"quanto tempo|quantos dias|qual (e )?o prazo|como funciona|o que acontece se", _MEDIUM),
        (r"how long|how does .* work", _MEDIUM),
    ),
    Intent.UNSUPPORTED: (
        (r"invers|invert|acciones de|cripto|investimento|investir|recomienda|recomenda", _STRONG),
        (r"aument(o|ar) (de |el |mi |o |do )?(limite|cupo)", _STRONG),
        (r"reembolso (ya|ahora)|devuelvan (mi|el) dinero|estorno (ja|imediato)|devolvam", _STRONG),
        (r"(hacer|haz|quiero) una transferencia|transferir|fazer uma transferencia|pagar (mi|a|la|o|minha)", _MEDIUM),
        (r"invest|increase my limit|transfer money", _STRONG),
    ),
    Intent.BALANCE_INQUIRY: ((r"\bsaldo|cuanto tengo|quanto tenho|balance", _MEDIUM),),
    Intent.PAYMENT_STATUS: ((r"(estado|status|situacao) de(l)? (mi |o |meu )?pago|meu pagamento", _MEDIUM),),
    Intent.STATEMENT_REQUEST: ((r"extracto|estado de cuenta|extrato|movimientos del mes", _MEDIUM),),
    Intent.CREDIT_PRODUCT_INFO: ((r"prestamo|emprestimo|credito personal|tarjeta de credito nueva|hipoteca", _MEDIUM),),
    Intent.CREDIT_ELIGIBILITY: ((r"(me )?(aprueban|califico|puedo pedir)|sou elegivel|posso pedir", _MEDIUM),),
    Intent.GREETING_OR_OTHER: ((r"^(hola|buen[oa]s|ola|oi|bom dia|boa tarde|boa noite|gracias|obrigad)", 0.55),),
}
_COMPILED = {
    intent: tuple((re.compile(pattern), weight) for pattern, weight in rules) for intent, rules in RULES.items()
}


def score(text: str) -> dict[Intent, float]:
    """Every matching intent with its score, for folded or raw ``text``."""
    folded = fold(text)
    scores: dict[Intent, float] = {}
    for intent, rules in _COMPILED.items():
        weights = sorted((weight for pattern, weight in rules if pattern.search(folded)), reverse=True)
        if weights:
            scores[intent] = min(0.99, weights[0] + 0.05 * (len(weights) - 1))
    return scores


class KeywordIntentRouter:
    """Implements ``IntentRouter``."""

    model = KEYWORD_ROUTER

    def __init__(self, threshold: float = THRESHOLD) -> None:
        self._threshold = threshold

    def route(self, text: UntrustedText, language: Language) -> IntentPrediction:
        scores = score(text)
        if not scores:
            scores = {Intent.GREETING_OR_OTHER: UNMATCHED_CONFIDENCE}
        ranked = sorted(scores.items(), key=lambda item: (-item[1], list(Intent).index(item[0])))
        top_intent, top_score = ranked[0]
        return IntentPrediction(
            intent=top_intent,
            confidence=top_score,
            candidates=tuple(IntentScore(intent=i, score=s) for i, s in ranked[:MAX_CANDIDATES]),
            below_threshold=top_score < self._threshold,
            model=KEYWORD_ROUTER,
        )
