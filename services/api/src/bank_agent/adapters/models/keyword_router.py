"""``router:keyword@1``: a transparent keyword baseline for the ``IntentRouter`` port (Spanish, Portuguese, English).

Each intent has weighted patterns over folded text (accents removed, lower case). An intent's score is its best
pattern weight, raised by 0.05 for every further matching pattern (at most 0.99). The prediction is the best
intent; ``below_threshold`` is true under ``THRESHOLD``. A message that matches nothing is ``greeting_or_other``
at 0.2, so the engine asks what the customer needs. Phase 10 replaces this with a learned router behind the port.
"""

import re
from collections.abc import Mapping

from bank_agent.application.understanding.extraction import CARD_STATE_QUESTION
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
        # QA 2026-10-05 (DSP-05): colloquial and regional phrasings ("cobro raro", "q yo no hize", "desconocer").
        (
            r"(cobro|cargo|compra|consumo|movimiento|cobranca)s? (raro|rara|extran[oa]|sospechos[oa]|estranh[oa])|"
            r"\b(q|que) (yo )?no (la |lo )?hi[cz]e\b|\bno (la |lo )?hi[cz]e\b|desconoc(er|i|io)\b|desconhec(er|i)\b",
            _STRONG,
        ),
        (
            r"(disputar|reclamar|desconocer|impugnar|contestar|objetar) (la|el|una|un|esta|este|esa|ese|a|o|essa|esse) "
            r"(compra|cargo|cobro|consumo|transaccion|cobranca|transacao|movimiento)|"
            r"(presentar|abrir|iniciar|levantar|poner|registrar?) (una |la |mi )?(reclamacion|aclaracion|disputa)|"
            r"(abrir|fazer|registrar) (uma )?(contestacao|reclamacao)",
            _STRONG,
        ),
    ),
    Intent.DISPUTE_STATUS: (
        (r"(estado|estatus|seguimiento) de (mi|la|mis|el) (reclam|aclarac|caso|disputa|desconoc)", _STRONG),
        (r"como va (mi|el|la) (reclam|caso|aclarac)|numero de caso", _STRONG),
        (r"(situacao|status|andamento) d[ao] (minha |meu )?(contestacao|caso|reclamacao)", _STRONG),
        (r"status of my (dispute|case)", _STRONG),
        # QA 2026-10-05 (DSP-03): pt-BR and colloquial status questions ("Como está a minha contestação?").
        (
            r"\b(como|cade|e) (esta |anda |vai |ficou |va |sigue |vamos con )?(a |o |el |la )?(minha |meu |mi |mis )?"
            r"(contestac|reclamac|aclarac|caso\b|disputa)|"
            r"(tengo|tenho|hay|existe) (alguna |algun |alguma |algum |una |um |uma )?"
            r"(reclamacion|aclaracion|contestacao|reclamacao|caso)( \w+)? "
            r"(abiert|abert|registrad|en curso|em andamento)",
            _STRONG,
        ),
        (
            r"(?<!solicitud )(?<!solicitacao )(?<!pedido )\b(quedo|fue|ficou|foi) registrad[ao]|"
            r"(cuando|plazo|prazo|quando)\b.{0,40}\b(respuesta|responder|responden|resposta|responderem|respondam)\b"
            r".{0,40}(contestac|reclam|aclarac|disputa|caso\b)",
            _MEDIUM,
        ),
    ),
    Intent.CARD_BLOCK: (
        (r"(?<!des)bloque(?!ad[oa])(ar|a|en|ame|o)|(?<!des)bloquei[aoe]|congel(ar|a)", _STRONG),
        (r"(?<!des)bloquead[oa]", _MEDIUM),
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
        (r"(mi tarjeta|meu cartao) (no |nao )?(esta|funciona|sirve|passa|pasa)|" + CARD_STATE_QUESTION, _STRONG),
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
        (r"(?<!libre )invers|invert|acciones de|cripto|investimento|investir|recomienda|recomenda", _STRONG),
        (r"aument(o|ar) (de |el |mi |o |do )?(limite|cupo)", _STRONG),
        (
            r"reembolso (ya|ahora)|devuelvan (mi|el) dinero|estorno (ja|imediato)|devolvam|contracargo|chargeback",
            _STRONG,
        ),
        (r"garantiz\w* (el |que me )?(reembolso|devuelvan)|garant\w* (o )?estorno", _STRONG),
        # QA 2026-10-05 (DSP-09): refund promises and a bare "estorno" are never promised by the assistant, and they
        # outrank the approval verb ("aprove o estorno" is not a credit request).
        (
            r"(van a|vas a|vai|vao) (regresar|devolver|reembolsar|reintegrar)|"
            r"me (regresan|devuelven|devolveran|regresaran|reembolsan)|(regresar|devolver)(me)? (mi|el) dinero|"
            r"(dinero|plata|dinheiro) (de vuelta|de volta|volta|vuelve)|\bestorno\b",
            _STRONG,
        ),
        (r"(hacer|haz|quiero) una transferencia|transferir|fazer uma transferencia|pagar (mi|a|la|o|minha)", _MEDIUM),
        (
            r"(fecha|dia) (limite )?de pago|vencimiento (de mi|del|de la) (pago|factura)|data de vencimento (da|do)|"
            r"(cuando|quando) (tengo que|debo|devo) pagar|cambiar (la )?fecha de (corte|pago)",
            0.95,
        ),
        (r"refinanc|reestructur|reestrutur|renegoci|desembols|portabilidad", _STRONG),
        (r"certificad|constancia|carta bancaria|declaracao bancaria", _STRONG),
        (r"invest|increase my limit|transfer money", _STRONG),
    ),
    Intent.BALANCE_INQUIRY: (
        (r"\bsaldos?\b|cuanto (dinero |plata )?tengo|quanto (dinheiro )?tenho|\bbalance\b", 0.8),
        (r"cuant[ao]s? (plata|lana|dinero|pesos|guita) (tengo|hay|me queda)", 0.8),
        (r"credito disponible|limite disponivel|cupo disponible|available credit", 0.8),
    ),
    Intent.PAYMENT_STATUS: (
        (
            r"(estado|status|situacao) d[aeo]l? (mi |minha |meu |la |a |o |sua |seu )?(pago|pagamento|transferencia)",
            0.85,
        ),
        (
            r"(se )?(realizo|hizo|llego|acredito|reflejo) (mi|la|el) (transferencia|pago)|"
            r"(minha|a) transferencia (foi|caiu|chegou|entrou)|(meu|o) pagamento (foi|caiu|entrou)",
            0.85,
        ),
        (r"status of my (payment|transfer)", 0.85),
        # QA 2026-10-05 (ACC-06): "el estado de mi última transferencia", "¿Mi transferencia sí se hizo?", "Cadê
        # minha transferência? ... não caiu". A missing transfer is a payment-status question, not a dispute.
        (
            r"(estado|status|situacao) d[aeo]l? (mi |minha |meu |la |a |o )?(ultim[ao] )?"
            r"(pago|pagamento|transferencia|pix)|"
            r"\b(mi|la|minha|a|meu|o) (ultim[ao] )?(transferencia|pago|pagamento|pix)\b.{0,25}"
            r"\b(se hizo|se realizo|llego|se acredito|salio|caiu|chegou|entrou|foi feit[ao])|"
            r"\bcade (a |o )?(minha |meu )?(transferencia|pix|pagamento)|"
            r"\b(pix|transferencia|pagamento)\b.{0,30}\bnao (caiu|chegou|entrou)",
            0.85,
        ),
    ),
    Intent.STATEMENT_REQUEST: (
        (
            r"extracto|estado de cuenta|extrato|movimientos (del|de este|de) mes|resumen de (mi |la )?(cuenta|tarjeta)|"
            r"resumo da (minha )?(conta|fatura)|movimentacoes|statement",
            0.8,
        ),
        # QA 2026-10-05 (ACC-07): the wording of ACC-ALL-2 itself ("resumen de movimientos").
        (
            r"resumen de (los |mis )?movimientos|movimientos de (mi|la) (cuenta|tarjeta)|"
            r"resumo (das|de) (minhas )?movimentac",
            0.8,
        ),
    ),
    Intent.CREDIT_PRODUCT_INFO: (
        (
            r"prestamo|emprestimo|credito personal|credito pessoal|tarjeta de credito nueva|hipoteca|"
            r"financiamento imobiliario|credito hipotecario|productos de credito|produtos de credito",
            0.75,
        ),
        (
            r"que (creditos|prestamos|tarjetas) (ofrecen|tienen|hay)|quais (creditos|emprestimos|cartoes)|"
            r"tasa de interes|taxa de juros|condiciones del|condicoes do|credit products",
            0.75,
        ),
        # QA 2026-10-05 (CRE-01, CRE-02, CRE-03, CRE-08): a bare "crédito", "libre inversión", "financiar", or a
        # score question belongs to credit. Card phrases ("tarjeta de crédito") and the available credit keep their
        # stronger rules; a score question is then abstained by the credit workflow's unsupported recognizer.
        (
            # "la de crédito" or "o de crédito" names a card or an account the customer already has, so any "a de" or
            # "o de" before the word (which also covers "tarjeta de" and "cartão de") keeps it out of this rule.
            r"(?<!tarjetas de )(?<!cartoes de )(?<!a de )(?<!o de )(?<!el de )(?<!limite de )(?<!cupo de )"
            r"\bcreditos?\b|libre inversion|\bfinanciar\b|\bscore\b|\bpuntaje\b|\bpontuacao\b|\bburo\b",
            0.65,
        ),
    ),
    Intent.CREDIT_ELIGIBILITY: (
        (
            r"(me )?(aprueban|califico|puedo pedir)|sou elegivel|posso pedir|(soy|seria) elegible|elegibilidad|"
            r"elegibilidade|puedo (sacar|solicitar|tener) (un|una)|me (dan|darian|daria) (un|una)|"
            r"consigo (um|uma|tirar)|am i eligible|"
            # Found on the dev split in phase 14b ("Posso pegar um empréstimo pessoal de 1.000.000 em 24 meses?").
            r"posso (pegar|tirar|conseguir|ter) (um|uma)|tenho direito a (um|uma)|tengo derecho a (un|una)|"
            r"puedo (obtener|conseguir) (un|una)|"
            # QA 2026-10-05 (CRE-02, CRE-03): "me prestan 10 palos", "Vocês me dão um cartão?", "Eu me qualifico?".
            r"\bme (prestan|prestarian|emprestam|emprestariam)\b|\bme (dao|da|daria|dariam) (um|uma)\b|\bqualifico\b",
            0.85,
        ),
        (r"\baprob|\baprueb|\baprov[ae]|\bapprove", 0.85),
    ),
    Intent.CREDIT_APPLICATION: (
        (
            r"(solicitar|pedir|sacar) (un|una) (prestamo|tarjeta|credito)|(solicitar|pedir|contratar) (um|uma) "
            r"(emprestimo|cartao)|registr(ar|a|en) (mi|la|a|minha) solicitud|registr(ar|e) (a|minha) solicitacao|"
            r"apply for (a|an)",
            0.85,
        ),
    ),
    Intent.CREDIT_APPLICATION_STATUS: (
        (
            r"(estado|status|situacao) d[aeo]l? (mi |la |el |minha |meu |a |o |sua |seu )?"
            r"(solicitud|solicitacao|pedido( de (credito|emprestimo|prestamo|cartao|tarjeta))?)\b|"
            r"como va mi solicitud|como esta (a )?minha solicitacao|"
            r"\bapp-[0-9a-z]{6,}",
            0.9,
        ),
    ),
    Intent.GREETING_OR_OTHER: ((r"^(hola|buen[oa]s|ola|oi|bom dia|boa tarde|boa noite|gracias|obrigad[oa])\b", 0.55),),
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
        if len(scores) > 1:
            # A greeting next to a request is the request (QA 2026-10-05, DSP-03: "Oi! Queria saber como está a
            # minha contestação" got the welcome message instead of the clarifying question).
            scores.pop(Intent.GREETING_OR_OTHER, None)
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
