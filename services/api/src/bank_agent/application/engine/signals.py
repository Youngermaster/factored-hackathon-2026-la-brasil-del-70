"""Escalation and privacy signals: a deterministic keyword detector in es and pt (distress includes financial
distress and over-indebtedness, which feed ``ESC.distress_signal``), merged with the optional
``detect_escalation_signals`` prompt. A signal counts when either source reports it; a gateway failure leaves the
deterministic result, so a missing model never hides a signal the keywords see."""

import re
from dataclasses import dataclass

from bank_agent.application.understanding.text import fold
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
_THIRD_PARTY = re.compile(
    r"\b(en nombre de|de parte de|em nome de|a pedido de|on behalf of)\b"
    r"|\b(tarjeta|cuenta|cartao|conta|compra|cargo)s? (de|da|do) (mi|minha|meu|una|um|uma) "
    r"(mama|madre|papa|padre|esposo|esposa|marido|mujer|hijo|hija|filho|filha|hermano|hermana|irmao|irma|abuela|"
    r"abuelo|avo|amigo|amiga|mae|pai|vecino|vecina|cliente)\b"
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


def detect_signals(text: str) -> DetectedSignals:
    folded = fold(text)
    return DetectedSignals(
        legal_or_regulator_mention=bool(_LEGAL.search(folded)),
        distress=bool(_DISTRESS.search(folded)),
        human_requested=bool(_HUMAN.search(folded)),
        third_party_admission=bool(_THIRD_PARTY.search(folded)),
    )
