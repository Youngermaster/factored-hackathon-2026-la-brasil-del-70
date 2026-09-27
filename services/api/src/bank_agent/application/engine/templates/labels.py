"""Customer-facing labels for codes (workflows, reasons, statuses, card types), in es, pt, and en."""

from collections.abc import Sequence

from bank_agent.domain.dispute import DisputeReason, DisputeStatus
from bank_agent.domain.locale import Language
from bank_agent.domain.product import ProductStatus, ProductType
from bank_agent.domain.transaction import TransactionStatus, TransactionType
from bank_agent.domain.workflow import WorkflowId

ES, PT, EN = Language.ES, Language.PT, Language.EN
Labels = dict[Language, str]

CAPABILITIES: dict[WorkflowId, Labels] = {
    WorkflowId.DISPUTE: {
        ES: "presentar o consultar una reclamación por una transacción",
        PT: "abrir ou acompanhar uma contestação de transação",
        EN: "opening or following a transaction dispute",
    },
    WorkflowId.CARD_SUPPORT: {
        ES: "el estado de tus tarjetas y su bloqueo preventivo",
        PT: "a situação dos seus cartões e o bloqueio preventivo",
        EN: "your card status and a protective card block",
    },
    WorkflowId.ACCOUNT_INQUIRY: {
        ES: "saldos, pagos y resúmenes de cuenta",
        PT: "saldos, pagamentos e resumos da conta",
        EN: "balances, payments, and account summaries",
    },
    WorkflowId.CREDIT: {
        ES: "información sobre productos de crédito",
        PT: "informações sobre produtos de crédito",
        EN: "credit product information",
    },
}
TOPICS: dict[WorkflowId, Labels] = {
    WorkflowId.DISPUTE: {
        ES: "una reclamación por un cargo",
        PT: "uma contestação de cobrança",
        EN: "a disputed charge",
    },
    WorkflowId.CARD_SUPPORT: {ES: "tus tarjetas", PT: "os seus cartões", EN: "your cards"},
    WorkflowId.ACCOUNT_INQUIRY: {ES: "tus saldos y pagos", PT: "os seus saldos e pagamentos", EN: "your balances"},
    WorkflowId.CREDIT: {ES: "productos de crédito", PT: "produtos de crédito", EN: "credit products"},
}
PENDING: dict[WorkflowId, Labels] = {
    WorkflowId.DISPUTE: {ES: "tu reclamación en curso", PT: "a sua contestação em andamento", EN: "your dispute"},
    WorkflowId.CARD_SUPPORT: {ES: "la consulta de tu tarjeta", PT: "o pedido do seu cartão", EN: "your card request"},
    WorkflowId.ACCOUNT_INQUIRY: {ES: "tu consulta de cuenta", PT: "a sua consulta da conta", EN: "your inquiry"},
    WorkflowId.CREDIT: {ES: "tu consulta de crédito", PT: "a sua consulta de crédito", EN: "your credit request"},
}
REASONS: dict[DisputeReason, Labels] = {
    DisputeReason.UNRECOGNIZED: {ES: "no reconoces la compra", PT: "você não reconhece a compra", EN: "unrecognized"},
    DisputeReason.DUPLICATE: {ES: "cargo duplicado", PT: "cobrança duplicada", EN: "duplicate charge"},
    DisputeReason.WRONG_AMOUNT: {
        ES: "monto distinto al acordado",
        PT: "valor diferente do combinado",
        EN: "wrong amount",
    },
    DisputeReason.NOT_RECEIVED: {
        ES: "producto o servicio no recibido",
        PT: "produto ou serviço não recebido",
        EN: "not received",
    },
    DisputeReason.ATM_CASH_NOT_DISPENSED: {
        ES: "el cajero no entregó el efectivo",
        PT: "o caixa eletrônico não entregou o dinheiro",
        EN: "ATM cash not dispensed",
    },
    DisputeReason.SUBSCRIPTION_CANCELLED: {
        ES: "suscripción ya cancelada",
        PT: "assinatura já cancelada",
        EN: "cancelled subscription",
    },
    DisputeReason.OTHER: {ES: "otro motivo", PT: "outro motivo", EN: "other reason"},
}
CASE_STATUSES: dict[DisputeStatus, Labels] = {
    DisputeStatus.OPENED: {ES: "abierto", PT: "aberto", EN: "open"},
    DisputeStatus.IN_REVIEW: {ES: "en revisión", PT: "em análise", EN: "in review"},
    DisputeStatus.ESCALATED: {ES: "escalado", PT: "escalado", EN: "escalated"},
    DisputeStatus.RESOLVED: {ES: "resuelto", PT: "resolvido", EN: "resolved"},
    DisputeStatus.REJECTED: {ES: "rechazado", PT: "rejeitado", EN: "rejected"},
}
CARD_TYPES: dict[ProductType, Labels] = {
    ProductType.CREDIT_CARD: {ES: "tarjeta de crédito", PT: "cartão de crédito", EN: "credit card"},
    ProductType.DEBIT_CARD: {ES: "tarjeta de débito", PT: "cartão de débito", EN: "debit card"},
}
CARD_STATUSES: dict[ProductStatus, Labels] = {
    ProductStatus.ACTIVE: {ES: "activa", PT: "ativo", EN: "active"},
    ProductStatus.BLOCKED: {ES: "bloqueada", PT: "bloqueado", EN: "blocked"},
    ProductStatus.CLOSED: {ES: "cerrada", PT: "encerrado", EN: "closed"},
    ProductStatus.SUSPENDED: {ES: "suspendida", PT: "suspenso", EN: "suspended"},
}
PRODUCT_TYPES: dict[ProductType, Labels] = {
    ProductType.CHECKING_ACCOUNT: {ES: "cuenta corriente", PT: "conta corrente", EN: "checking account"},
    ProductType.SAVINGS_ACCOUNT: {ES: "cuenta de ahorro", PT: "conta poupança", EN: "savings account"},
    ProductType.CREDIT_CARD: {ES: "tarjeta de crédito", PT: "cartão de crédito", EN: "credit card"},
    ProductType.DEBIT_CARD: {ES: "tarjeta de débito", PT: "cartão de débito", EN: "debit card"},
    ProductType.PERSONAL_LOAN: {ES: "préstamo personal", PT: "empréstimo pessoal", EN: "personal loan"},
    ProductType.MORTGAGE: {ES: "crédito hipotecario", PT: "financiamento imobiliário", EN: "mortgage"},
    ProductType.INVESTMENT: {ES: "inversión", PT: "investimento", EN: "investment"},
    ProductType.OTHER: {ES: "producto", PT: "produto", EN: "product"},
}
PAYMENT_KINDS: dict[TransactionType, Labels] = {
    TransactionType.TRANSFER: {ES: "tu transferencia", PT: "da sua transferência", EN: "your transfer"},
    TransactionType.PAYMENT: {ES: "tu pago", PT: "do seu pagamento", EN: "your payment"},
}
PAYMENT_STATUSES: dict[TransactionStatus, Labels] = {
    TransactionStatus.APPROVED: {ES: "completado", PT: "concluída", EN: "completed"},
    TransactionStatus.PENDING: {ES: "pendiente", PT: "pendente", EN: "pending"},
    TransactionStatus.DECLINED: {ES: "rechazado", PT: "recusada", EN: "declined"},
    TransactionStatus.REVERSED: {ES: "revertido", PT: "estornada", EN: "reversed"},
}
_AND = {ES: "y", PT: "e", EN: "and"}


def join(items: Sequence[str], language: Language) -> str:
    """``a, b y c`` in Spanish, ``a, b e c`` in Portuguese, ``a, b and c`` in English."""
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} {_AND[language]} {items[-1]}"


def pick(labels: Labels, language: Language) -> str:
    """The label in ``language`` (Spanish when a label has no text in it)."""
    return labels.get(language) or labels[ES]
