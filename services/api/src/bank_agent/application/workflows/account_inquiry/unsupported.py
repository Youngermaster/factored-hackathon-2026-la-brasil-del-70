"""Account requests the workflow does not handle (``ACC-ALL-3``): transfers, bill payments, due date changes, due
dates the records do not hold, and official statements or certificates. They are abstained with ``ACC-ALL-3`` and an
offer of a human, whether the router sent them here or to the out-of-scope handler."""

import re

from bank_agent.application.engine.definition import UnsupportedRequest
from bank_agent.application.understanding.text import fold

CLAUSES = ("ACC-ALL-3",)
_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "transfer",
        re.compile(
            r"\b(hacer|haz|hace|realizar|mandar|enviar|quiero|quisiera|necesito)\b.{0,20}\btransferencia\b|"
            r"\btransferir\b|\bfazer (uma )?transferencia|\b(quero|preciso) (fazer|mandar)\b.{0,15}\btransferencia|"
            r"\b(mandar|enviar) (dinheiro|dinero|plata)\b|\bfazer um pix\b|\btransfer money\b|"
            # An imperative with money in it ("Transfiere 2000 pesos de mi cuenta de ahorro a la corriente", found on
            # the dev split in phase 14b); "transfiérame con un asesor" names no money and is not a transfer.
            r"\b(transfiere|transfiera|transferi|transfira|transfere|transfiri)\b.{0,25}"
            r"(\d|\bpesos\b|\breais\b|\bdinero\b|\bdinheiro\b|\bplata\b|\blucas\b|\bde mi cuenta\b|\bda minha conta\b)"
        ),
    ),
    (
        "bill_payment",
        re.compile(
            r"\bpagar (mi|la|el|mis|las|los|o|a|minha|meu|minhas|meus|uma|um) ?(tarjeta|factura|recibo|cuenta|"
            r"servicio|luz|agua|boleto|fatura|conta|cartao|prestamo|emprestimo)|\bpay my (bill|card)\b"
        ),
    ),
    (
        "due_date_change",
        re.compile(r"\b(cambiar|mover|modificar|mudar|alterar) (la |a )?(fecha|data|dia) de (corte|pago|vencimento)"),
    ),
    (
        "due_date",
        re.compile(
            r"\b(fecha|dia) (limite )?de pago\b|\bvencimiento (de mi|del|de la) (pago|factura)|"
            r"\bdata de vencimento (da|do) (fatura|boleto|pagamento)|\b(cuando|quando) (tengo que|debo|devo) pagar"
        ),
    ),
    (
        "certificate",
        re.compile(
            r"\bcertificad|\bconstancia\b|\bcarta (bancaria|de referencia)|\b(extracto|estado de cuenta|extrato) "
            r"(oficial|sellado|firmado|assinado)|\bdeclaracao (bancaria|de saldo)|\bcomprovante oficial"
        ),
    ),
)


def recognize(text: str) -> UnsupportedRequest | None:
    folded = fold(text)
    for code, pattern in _PATTERNS:
        if pattern.search(folded):
            return UnsupportedRequest(code=code, clauses=CLAUSES)
    return None
