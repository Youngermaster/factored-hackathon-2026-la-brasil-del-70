"""Escalation and privacy signals: a deterministic keyword detector in es and pt (distress includes financial
distress and over-indebtedness, which feed ``ESC.distress_signal``), merged with the optional
``detect_escalation_signals`` prompt. A signal counts when either source reports it; a gateway failure leaves the
deterministic result, so a missing model never hides a signal the keywords see."""

import re
from dataclasses import dataclass

from bank_agent.application.understanding.answers import YesNo, parse_yes_no
from bank_agent.application.understanding.text import fold, words
from bank_agent.domain.llm_outputs import EscalationSignals as ModelSignals

SIGNAL_DETECTOR = "signals:keyword@1"
_LEGAL = re.compile(
    r"\b(condusef|profeco|superintendencia|superfinanciera|banco central|bcra|bacen|banxico|defensa del consumidor|"
    r"defensoria|procon|reclame aqui|consumidor gov|abogad[oa]|advogad[oa]|demanda\w*|denuncia\w*|processar|"
    r"processo judicial|juicio|tribunal|juzgado|justicia|justica|regulador\w*|ombudsman|lawyer|sue|court)\b"
)
_DISTRESS = re.compile(
    r"\b(desesperad[oa]|angustiad[oa]|no tengo (para|con que) comer|no se que hacer|nao sei o que fazer|panico|"
    r"me amenaza\w*|estoy en peligro|socorro|me estan presionando|me presionan|estou sendo pressionad[oa]|"
    r"chorando|llorando|emergencia medica|hospital|me quiero morir|desperate|panic)\b"
    r"|\b(no puedo pagar (mis|las|mi) deudas?|no me alcanza para pagar|estoy (muy |super )?endeudad[oa]|"
    r"sobreendeudad[oa]|ahogad[oa] (en|con) deudas|no llego a fin de mes|superendividad[oa]|"
    r"(estou|to|tou) (muito )?endividad[oa]|nao consigo pagar (minhas|as|meus) (dividas|contas)|"
    r"afogad[oa] em dividas|over.?indebted|cannot pay my debts)\b"
)
_HUMAN = re.compile(
    r"\b(hablar con (una persona|un humano|un asesor|alguien|un agente|un ejecutivo)|asesor humano|agente humano|"
    r"falar com (uma pessoa|um atendente|um humano|alguem)|atendente humano|talk to (a person|a human|an agent))\b"
)
_RELATIVE = (
    r"(?:mama|madre|papa|padre|esposo|esposa|marido|mujer|pareja|hijo|hija|filho|filha|hermano|hermana|irmao|irma|"
    r"abuela|abuelo|avo|nieto|nieta|neto|neta|tio|tia|primo|prima|suegro|suegra|sogro|sogra|novio|novia|namorado|"
    r"namorada|amigo|amiga|mae|pai|vecino|vecina|vizinho|vizinha|jefe|chefe|socio|socia|cliente)"
)
# A product first ("la tarjeta de crédito de mi mamá", "o cartão de crédito da minha mãe", "o saldo da conta dele"):
# the product noun, up to three qualifier words from a closed list, then the owner. Phase 14b added it after the dev
# split showed P offering to block the customer's own card for a relative's card. A purchase or a charge keeps the
# owner right after the noun, so "la compra de los útiles de mi hijo" (the customer's own purchase) is not a signal.
_PRODUCT = r"(?:tarjeta|cuenta|cartao|conta|prestamo|emprestimo|credito|saldo|limite|financiamiento|financiamento)s?"
_QUALIFIER = (
    r"(?:de|do|da|del|la|el|a|o|su|sua|seu|credito|debito|ahorros?|corriente|corrente|poupanca|sueldo|nomina|"
    r"salario|adicional|virtual|fisica|visa|mastercard|oro|dorada|platinum|clasica|gold|black|personal|pessoal|"
    r"hipotecario|imobiliario|cuenta|conta|tarjeta|cartao|prestamo|emprestimo)"
)
_OWNER = rf"(?:de|da|do|del|dos|das) (?:mi|mis|minha|minhas|meu|meus|una|um|uma) {_RELATIVE}s?"
_THIRD_PARTY = re.compile(
    r"\b(?:en nombre de|de parte de|em nome d[eoa]s?|a pedido d[eoa]s?|on behalf of)\b"
    r"|\b(?:apoderad[oa]|procurador[a]?|poder notarial|procuracao) (?:de|da|do|del)\b"
    rf"|\b(?:compra|cargo|cobro|cobranca)s? {_OWNER}\b"
    rf"|\b{_PRODUCT} (?:{_QUALIFIER} ){{0,3}}(?:{_OWNER}|dele|dela|deles|delas)\b"
)


@dataclass(frozen=True)
class DetectedSignals:
    legal_or_regulator_mention: bool = False
    distress: bool = False
    human_requested: bool = False
    third_party_admission: bool = False

    def merged(self, model: ModelSignals | None) -> "DetectedSignals":
        if model is None:
            return self
        return DetectedSignals(
            legal_or_regulator_mention=self.legal_or_regulator_mention or model.legal_or_regulator_mention,
            distress=self.distress or model.distress,
            human_requested=self.human_requested or model.human_requested,
            third_party_admission=self.third_party_admission or model.third_party_admission,
        )


MAX_ACCEPTANCE_WORDS = 4


def accepts_offer(text: str) -> bool:
    """A bare yes ("sí", "sim", "claro", "sí, por favor"): the answer to an offer of a person, nothing more."""
    return len(words(text)) <= MAX_ACCEPTANCE_WORDS and parse_yes_no(text) is YesNo.YES


def detect_signals(text: str, *, person_offered: bool = False) -> DetectedSignals:
    """The keyword signals of ``text``; after an offer of a person, a bare yes is a request for one."""
    folded = fold(text)
    return DetectedSignals(
        legal_or_regulator_mention=bool(_LEGAL.search(folded)),
        distress=bool(_DISTRESS.search(folded)),
        human_requested=bool(_HUMAN.search(folded)) or (person_offered and accepts_offer(text)),
        third_party_admission=bool(_THIRD_PARTY.search(folded)),
    )
