"""Baseline B0 fixed strings: a Spanish menu with one fixed Portuguese line, and a fixed reason menu."""

from bank_agent.application.engine.templates import register
from bank_agent.domain.locale import Language

ES, PT, EN = Language.ES, Language.PT, Language.EN

BASELINE_TEMPLATES: dict[str, dict[Language, str]] = {
    "b0.menu": {
        ES: "Menú principal. Escribe una opción: saldo, estado de un pago, estado de cuenta, reclamar un cargo, "
        "estado de una reclamación, estado de tarjeta, bloquear tarjeta, productos de crédito o hablar con una "
        "persona.",
        PT: "Menu principal (somente em espanhol).",
        EN: "Main menu. Write an option: balance, payment status, statement, dispute a charge, dispute status, card "
        "status, block card, credit products, or talk to a person.",
    },
    "b0.reasons": {
        ES: "Escribe el motivo: no reconozco, duplicado, monto distinto, no recibido, cajero o suscripción.",
        PT: "Escreva o motivo em espanhol.",
        EN: "Write the reason: unrecognized, duplicate, wrong amount, not received, ATM, or subscription.",
    },
}
register(BASELINE_TEMPLATES)
