"""Escalation and privacy signals: a deterministic keyword detector in es and pt (distress includes financial
distress and over-indebtedness, which feed ``ESC.distress_signal``), merged with the optional
``detect_escalation_signals`` prompt. A signal counts when either source reports it; a gateway failure leaves the
deterministic result, so a missing model never hides a signal the keywords see.

The third-party signal (``PRV.no_third_party_disclosure``) covers a relative or a representative, and another
customer or another person named by wording or by a document number (``names_another_customer``)."""

import re
from dataclasses import dataclass

from bank_agent.application.understanding.answers import YesNo, parse_yes_no
from bank_agent.application.understanding.text import fold, words
from bank_agent.domain.llm_outputs import EscalationSignals as ModelSignals

SIGNAL_DETECTOR = "signals:keyword@1"
_LEGAL = re.compile(
    r"\b(condusef|profeco|superintendencia|superfinanciera|banco central|bcra|bacen|banxico|defensa del consumidor|"
    r"defensoria|procon|reclame aqui|consumidor gov|abogad[oa]|advogad[oa]|demanda\w*|denuncia\w*|processar|"
    r"processo judicial|juicio|tribunal|juzgado|justicia|justica|regulador\w*|ombudsman|lawyer|sue|court|"
    r"autoridad(?:es)?|autoridades?|defensor del consumidor\w*|ouvidoria)\b"
)
# The bank's own dispute vocabulary ("reclamación" is the word the bot itself uses for a dispute, and a Colombian
# PQR). A small model read "¿Cómo va mi reclamación?" as a formal complaint body and escalated it as a legal or
# regulator mention (QA finding DSP-01). When the text has these words and no legal or authority hint, the model's
# legal flag is dropped; the keyword list above still escalates on its own.
_BANK_COMPLAINT = re.compile(
    r"\b(reclam\w*|aclarac\w*|contest\w*|disput\w*|desconoc\w*|desconhec\w*|queja\w*|queix\w*)"
)
_AUTHORITY_HINT = re.compile(
    r"\b(legal\w*|judicial\w*|juridic\w*|formal\w*|instancia\w*|autoridad\w*|autoridade\w*|denunc\w*|demand\w*|"
    r"policia|fiscalia|gobierno|governo|ministerio|extern\w*|superior\w*|super\w*|sic|sfc|defensor\w*|"
    r"defensoria|ouvidoria|procon|condusef|profeco|bacen|bcra|banxico|banco central|regulador\w*|ombudsman|"
    r"tribunal|juzgado|juicio|justic\w*|abogad\w*|advogad\w*|reclame aqui|consumidor)\b"
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
# A demand for a credit decision said with urgency ("Apruébame el préstamo personal ya, ándale, lo necesito hoy",
# "Aprova meu empréstimo, preciso hoje"). The model read the urgency as distress, and ESC.distress_signal escalated
# with the 4-hour priority before the credit workflow could abstain with CRE-ALL-3 (QA finding CRE-16). Urgency
# about a request is not distress by itself: with an approval demand and urgency words, the model's distress flag is
# dropped, and the keyword distress list above (hardship, health, threats, over-indebtedness) still escalates.
_APPROVAL_DEMAND = re.compile(
    r"\b(apruebame\w*|aprobame\w*|apruebe(n|nme)?|aprueba(lo|la|me)?|aprobar(me|lo|la)?|me (lo |la )?aprueban|"
    r"aprova(r)?|aprove(m)?|aprovem|me aprova|aprova(-| )?me|desembols\w*|"
    r"libera(me)? (el|o) (credito|prestamo|emprestimo)|"
    r"dame el (credito|prestamo)|me (da|de) o (credito|emprestimo))\b"
)
_URGENCY = re.compile(
    r"\b(urgente\w*|urgencia|ya|ja|hoy|hoje|ahora|agora|ahorita|rapido|rapidinho|de inmediato|imediatamente|"
    r"andale|lo necesito|la necesito|preciso|necessito|ya mismo|agorinha|pronto)\b"
)
# Moving the customer's own money to a relative ("Faz um pix de 300 reais pro meu irmão", "Pásale 2000 pesos a mi
# hermana"): the relative is the recipient, not the owner of a product or of data. The model flagged these as third
# party, the kernel refused them with PRV-ALL-2 and the raised risk tier asked for step-up on the next read (QA
# finding ACC-04). With a transfer verb and the relative as the recipient, the model's third-party flag is dropped;
# the keyword detector above still refuses a relative's product ("la cuenta de mi mamá").
_MONEY_MOVEMENT = re.compile(
    r"\b(transfer\w*|transfi\w*|pix|deposit\w*|pasale\w*|pasarle\w*|mandale\w*|enviale\w*|transfierele)\b"
    r"|\b(mand[aeo]|mandar|envi[aeo]|enviar|faz|faca|fazer|paga|pagar|presta|prestar|empresta|emprestar)\b"
    r".{0,40}(\d|\b(dinero|dinheiro|plata|pesos?|reais|real|dolares?|grana|lana)\b)"
)
_TO_RELATIVE = re.compile(
    rf"\b(?:a|al|para|pra|pro|pros|pras|ao|aos|as) (?:mi|mis|meu|minha|meus|minhas) {_RELATIVE}s?\b"
)
# Another customer or another person named as the owner ("la tarjeta del cliente CC 1234567890", "o saldo de outro
# cliente", "da pessoa com CPF"): added before the pitch video, when such requests got the workflow question. Tools
# never take a customer id, so nothing leaked; the request is now refused with PRV-ALL-2 before any tool runs.
# "servicio al cliente" and "número de cliente" (the customer's own number) have no article and do not match.
_OTHER_CUSTOMER = re.compile(
    r"\b(?:otr[oa]s?|outr[oa]s?) (?:client[ea]s?|usuari[oa]s?|cuentahabientes?|correntistas?|titular(?:es)?)\b"
    r"|\b(?:del|de la|de un|de una|do|da|de um|de uma) (?:client[ea]|cuentahabiente|correntista)\b"
    r"|\b(?:de|da|del) (?:la |una |esa |esta |uma |essa |otra |outra )?(?:persona|pessoa|senora|senhora|senor"
    r"|senhor) (?:con|com|que tiene|que tem|cuy[oa]|cuja|cujo)\b"
    rf"|\b{_PRODUCT} (?:{_QUALIFIER} ){{0,3}}(?:de|da|do|del) (?:otra|outra) (?:persona|pessoa)\b"
    r"|\b(?:another|other) (?:customer|client)s?\b|\b(?:another|other) person'?s\b|\bsomeone else'?s\b"
    r"|\b(?:of|for) (?:the |a )?(?:customer|client) (?:with|number|id)\b"
)
# A document number introduced by its kind ("CC 1234567890", "cédula 12.345.678", "CPF 123.456.789-00", "DNI:
# 30123456") or written in a document format (CPF, CURP). The customer's own document ("mi cédula es ...", "meu
# CPF") is not a signal: identity comes from the session either way, and the reply never repeats the number.
_DOCUMENT = re.compile(
    r"(?<![a-z0-9])(?:c\.\s?c\.?|cc|cedula(?: de ciudadania| de identidad)?|dni|cpf|rg|curp|rfc|cuit|cuil|nit|ine"
    r"|pasaporte|passaporte|documento(?: de identidad| nacional)?|identidade|identificacion)(?![a-z])"
    r"(?:\s*(?:n[o.]?|numero|nro\.?|#|:|es|e|nº|n°))*\s*(?P<number>\d[\d.\- ]{4,18}\d)(?!\d)"
    r"|(?<![a-z0-9])[a-z]{4}\d{6}[hmx][a-z]{5}[a-z0-9]\d(?![a-z0-9])"
    r"|(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)"
)
_OWN_DOCUMENT = re.compile(r"\b(?:mi|mis|meu|meus|minha|minhas|my|el mio|o meu)\s*$")
OWN_DOCUMENT_WINDOW = 24
"""Characters before a document mention searched for a possessive ("mi número de cédula", "o meu CPF")."""


def names_another_customer(folded: str) -> bool:
    """True when ``folded`` text asks about another customer or another person by wording or a document number."""
    if _OTHER_CUSTOMER.search(folded):
        return True
    for match in _DOCUMENT.finditer(folded):
        before = folded[max(0, match.start() - OWN_DOCUMENT_WINDOW) : match.start()]
        if not _OWN_DOCUMENT.search(before.replace("numero de ", "")):
            return True
    return False


@dataclass(frozen=True)
class DetectedSignals:
    legal_or_regulator_mention: bool = False
    distress: bool = False
    human_requested: bool = False
    third_party_admission: bool = False
    urgent_decision_demand: bool = False
    """The text demands a credit decision with urgency and has no keyword distress; the model's distress flag is then
    not trusted on its own."""
    transfer_to_relative: bool = False
    """The text moves the customer's own money to a relative (the recipient); the model's third-party flag is then
    not trusted on its own."""
    bank_complaint_only: bool = False
    """The text uses the bank's own dispute words ("reclamación", "contestação") with no legal or authority hint;
    the model's legal flag is then not trusted on its own."""

    def merged(self, model: ModelSignals | None) -> "DetectedSignals":
        if model is None:
            return self
        model_legal = model.legal_or_regulator_mention and not self.bank_complaint_only
        model_third_party = model.third_party_admission and not self.transfer_to_relative
        model_distress = model.distress and not self.urgent_decision_demand
        return DetectedSignals(
            legal_or_regulator_mention=self.legal_or_regulator_mention or model_legal,
            distress=self.distress or model_distress,
            human_requested=self.human_requested or model.human_requested,
            third_party_admission=self.third_party_admission or model_third_party,
            urgent_decision_demand=self.urgent_decision_demand,
            transfer_to_relative=self.transfer_to_relative,
            bank_complaint_only=self.bank_complaint_only,
        )


MAX_ACCEPTANCE_WORDS = 4


def accepts_offer(text: str) -> bool:
    """A bare yes ("sí", "sim", "claro", "sí, por favor"): the answer to an offer of a person, nothing more."""
    return len(words(text)) <= MAX_ACCEPTANCE_WORDS and parse_yes_no(text) is YesNo.YES


MAX_ANSWER_WORDS = 6


def plain_answer(text: str) -> bool:
    """A short yes or no ("Sí, quiero solicitarlo", "não, obrigado"): an answer to a pending question, nothing more.

    At a pending question such a turn is resolved by the deterministic parsers alone; the model's escalation
    signals are not asked for, because a small model read "Sí, quiero solicitarlo" as a request for a person
    (phase 14b). The keyword signals still run on it, so "sí, pero quiero hablar con un asesor" still escalates."""
    return len(words(text)) <= MAX_ANSWER_WORDS and parse_yes_no(text) is not YesNo.UNCLEAR


def detect_signals(text: str, *, person_offered: bool = False) -> DetectedSignals:
    """The keyword signals of ``text``; after an offer of a person, a bare yes is a request for one."""
    folded = fold(text)
    distress = bool(_DISTRESS.search(folded))
    return DetectedSignals(
        legal_or_regulator_mention=bool(_LEGAL.search(folded)),
        distress=distress,
        human_requested=bool(_HUMAN.search(folded)) or (person_offered and accepts_offer(text)),
        third_party_admission=bool(_THIRD_PARTY.search(folded)) or names_another_customer(folded),
        urgent_decision_demand=not distress and bool(_APPROVAL_DEMAND.search(folded)) and bool(_URGENCY.search(folded)),
        transfer_to_relative=bool(_MONEY_MOVEMENT.search(folded)) and bool(_TO_RELATIVE.search(folded)),
        bank_complaint_only=bool(_BANK_COMPLAINT.search(folded)) and not _AUTHORITY_HINT.search(folded),
    )
