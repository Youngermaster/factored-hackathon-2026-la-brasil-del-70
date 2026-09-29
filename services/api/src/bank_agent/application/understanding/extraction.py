"""Deterministic slot extraction, the fallback when the language model is off or fails.

It reads what the customer said about a transaction or a card in Spanish and Portuguese: the dispute reason and
the block reason from keyword tables, a card ending ("terminada en 1234"), the channel, and a merchant phrase (the
words after "en", "na", "no", "em" or "at", cut before dates, amounts, and connectors). It never guesses beyond
the text: an unknown slot stays ``None``.
"""

import re

from bank_agent.application.understanding.text import fold
from bank_agent.domain.cards import CardAction, CardBlockReason
from bank_agent.domain.dispute import DisputeReason
from bank_agent.domain.product import ProductType
from bank_agent.domain.transaction import TransactionChannel

_REASONS: tuple[tuple[DisputeReason, str], ...] = (
    (
        DisputeReason.ATM_CASH_NOT_DISPENSED,
        r"cajero|caixa eletronico|caixa 24|atm\b|no (me )?(dio|entrego) (el )?(dinero|efectivo)",
    ),
    (DisputeReason.DUPLICATE, r"duplicad|dos veces|duas vezes|doble|cobrado dos|cobraram duas"),
    (DisputeReason.SUBSCRIPTION_CANCELLED, r"suscripcion|assinatura|ya cancele|ja cancelei"),
    (
        DisputeReason.NOT_RECEIVED,
        r"no (me )?(llego|recibi)|nunca (llego|recibi)|nao (me )?(chegou|recebi)|nunca chegou",
    ),
    (
        DisputeReason.WRONG_AMOUNT,
        r"monto (distinto|incorrecto|equivocado)|de mas\b|valor (errado|diferente|incorreto)|a mais\b|mas de lo",
    ),
    (
        DisputeReason.UNRECOGNIZED,
        r"no (la |lo )?reconozco|desconozco|no fui yo|no (la |lo )?hice|nao (a |o )?reconheco|nao fui eu|"
        r"desconheco|nao fiz|fraude|no autorice|nao autorizei",
    ),
)
_BLOCK_REASONS: tuple[tuple[CardBlockReason, str], ...] = (
    (CardBlockReason.STOLEN, r"robaron|robo|robada|robado|roubaram|roubo|roubad[oa]|asaltaron|assaltaram"),
    (CardBlockReason.LOST, r"perdi|extravi|perdida|perdido|perdeu|nao encontro|no encuentro|no la encuentro"),
    (
        CardBlockReason.UNRECOGNIZED_ACTIVITY,
        r"no reconozco|nao reconheco|movimientos raros|movimentos estranhos|fraude",
    ),
    (CardBlockReason.PRECAUTION, r"precaucion|prevencion|por si acaso|precaucao|prevencao|por seguranca|por seguridad"),
)
CARD_STATE_QUESTION = (
    r"\b(?:esta|estan|estao|sigue|siguen|continua|continuam|se encuentra|se encontra|quedo|ficou|fue|foi)"
    r"(?: [a-z0-9]+){0,4}? bloquead[oa]s?\b"
    r"|\b(?:activ|ativ)[ao]s? (?:o|ou) bloquead[oa]s?\b|\bbloquead[oa]s? (?:o|ou) (?:activ|ativ)[ao]s?\b"
)
"""A question about a card's state that uses the participle ("¿está bloqueada?", "ativo ou bloqueado?"), over
folded text. It asks for the card status and is never a block request, so the action table and the keyword router
read it as status."""
_STATE_QUESTION = re.compile(CARD_STATE_QUESTION)
_ACTIONS: tuple[tuple[CardAction, str], ...] = (
    (CardAction.UNBLOCK_REQUEST, r"desbloque|desbloquei|reactiv|reativ"),
    (CardAction.REPLACEMENT_REQUEST, r"reposicion|reponer|reemplaz|reposicao|segunda via|substitu|nuev[ao]|novo|nova"),
    (CardAction.BLOCK, r"(?<!des)bloque|(?<!des)bloquei|congel|cancel(a|ar) (la|mi|o|meu)"),
)
_CHANNELS: tuple[tuple[TransactionChannel, str], ...] = (
    (TransactionChannel.ATM, r"cajero|caixa eletronico|atm\b"),
    (TransactionChannel.WEB, r"internet|en linea|online|pagina web|site\b"),
    (TransactionChannel.APP, r"\bapp\b|aplicacion|aplicativo"),
    (TransactionChannel.POS, r"tienda|comercio|loja|supermercado|super\b|restaurante"),
)
_LAST4 = re.compile(r"(?:terminad[ao]|termina|final|finalizad[ao]|acabad[ao]|ending)(?: en| em| in)? (\d{4})\b")
_MERCHANT = re.compile(
    r"\b(?:en|na|em|at|no mercado|no posto|no restaurante)\s+(?:el |la |los |las |o |a |os |as )?"
    r"(?P<name>[a-z0-9&.' ]{3,60})"
)
_STOP = re.compile(
    r"\b(?:ayer|hoy|anteayer|antier|ontem|hoje|el|la|los|las|por|de|del|que|y|e|con|com|pero|mas|mi|meu|minha|"
    r"tarjeta|cartao|cuenta|conta|hace|ha|faz|semana|mes|lunes|martes|miercoles|jueves|viernes|sabado|domingo|"
    r"segunda|terca|quarta|quinta|sexta|\d+)\b.*"
)


def _first[T](table: tuple[tuple[T, str], ...], folded: str) -> T | None:
    return next((value for value, pattern in table if re.search(pattern, folded)), None)


def dispute_reason(text: str) -> DisputeReason | None:
    return _first(_REASONS, fold(text))


def block_reason(text: str) -> CardBlockReason | None:
    return _first(_BLOCK_REASONS, fold(text))


def asks_card_state(text: str) -> bool:
    return _STATE_QUESTION.search(fold(text)) is not None


def card_action(text: str) -> CardAction | None:
    """The card action asked for; a state question ("¿está bloqueada?") is removed first, so it is no block."""
    return _first(_ACTIONS, _STATE_QUESTION.sub(" ", fold(text)))


def channel(text: str) -> TransactionChannel | None:
    return _first(_CHANNELS, fold(text))


def card_last4(text: str) -> str | None:
    match = _LAST4.search(fold(text))
    return match.group(1) if match else None


def card_type(text: str) -> ProductType | None:
    folded = fold(text)
    if re.search(r"credito", folded):
        return ProductType.CREDIT_CARD
    if re.search(r"debito", folded):
        return ProductType.DEBIT_CARD
    return None


def merchant_phrase(text: str) -> str | None:
    """The words naming a merchant, at most three, or ``None``."""
    for match in _MERCHANT.finditer(fold(text)):
        name = _STOP.sub("", match.group("name")).strip(" .,'")
        words = [word for word in name.split() if len(word) >= 3][:3]
        if words:
            return " ".join(words)
    return None
