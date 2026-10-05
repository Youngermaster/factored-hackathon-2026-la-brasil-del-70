"""Customer-facing labels for codes (workflows, reasons, statuses, card types), in es, pt, and en."""

from collections.abc import Sequence

from bank_agent.domain.credit import ApplicationStatus, CreditProductType
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
    DisputeReason.UNRECOGNIZED: {
        ES: "no reconoces la transacción",
        PT: "você não reconhece a transação",
        EN: "unrecognized",
    },
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
PRODUCT_OF_YOUR: dict[ProductType, Labels] = {
    ProductType.CHECKING_ACCOUNT: {ES: "tu cuenta corriente", PT: "da sua conta corrente", EN: "your checking account"},
    ProductType.SAVINGS_ACCOUNT: {ES: "tu cuenta de ahorro", PT: "da sua conta poupança", EN: "your savings account"},
    ProductType.CREDIT_CARD: {ES: "tu tarjeta de crédito", PT: "do seu cartão de crédito", EN: "your credit card"},
    ProductType.DEBIT_CARD: {ES: "tu tarjeta de débito", PT: "do seu cartão de débito", EN: "your debit card"},
    ProductType.PERSONAL_LOAN: {ES: "tu préstamo personal", PT: "do seu empréstimo pessoal", EN: "your personal loan"},
    ProductType.MORTGAGE: {
        ES: "tu crédito hipotecario",
        PT: "do seu financiamento imobiliário",
        EN: "your mortgage",
    },
    ProductType.INVESTMENT: {ES: "tu inversión", PT: "do seu investimento", EN: "your investment"},
    ProductType.OTHER: {ES: "tu producto", PT: "do seu produto", EN: "your product"},
}
"""A product with its possessive, agreeing in gender in pt ("da sua conta poupança", "do seu cartão"; ACC-11)."""
NO_MERCHANT: Labels = {ES: "sin comercio registrado", PT: "sem estabelecimento registrado", EN: "no merchant on record"}
"""Shown instead of a merchant the record does not have (an ATM withdrawal; DSP-10)."""
NO_PAYEE: Labels = {ES: "sin destinatario registrado", PT: "sem destinatário registrado", EN: "no payee on record"}
"""Shown instead of a payee the record does not have (a transfer without a merchant name; ACC-10)."""
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
CREDIT_TYPES: dict[CreditProductType, Labels] = {
    CreditProductType.CREDIT_CARD: {ES: "tarjeta de crédito", PT: "cartão de crédito", EN: "credit card"},
    CreditProductType.PERSONAL_LOAN: {ES: "préstamo personal", PT: "empréstimo pessoal", EN: "personal loan"},
    CreditProductType.MORTGAGE: {ES: "crédito hipotecario", PT: "financiamento imobiliário", EN: "mortgage"},
}
PURPOSES: dict[str, Labels] = {
    "general_purpose": {ES: "uso general", PT: "uso geral", EN: "general purpose"},
    "debt_consolidation": {ES: "consolidar deudas", PT: "consolidar dívidas", EN: "debt consolidation"},
    "home_improvement": {ES: "mejoras del hogar", PT: "reformas da casa", EN: "home improvement"},
    "education": {ES: "educación", PT: "educação", EN: "education"},
    "home_purchase": {ES: "compra de vivienda", PT: "compra de imóvel", EN: "home purchase"},
    "home_construction": {ES: "construcción de vivienda", PT: "construção de imóvel", EN: "home construction"},
}
APPLICATION_STATUSES: dict[ApplicationStatus, Labels] = {
    ApplicationStatus.SUBMITTED: {ES: "registrada, en espera de revisión", PT: "registrada, aguardando análise",
                                  EN: "recorded, awaiting review"},
    ApplicationStatus.UNDER_HUMAN_REVIEW: {ES: "en revisión por una persona del equipo",
                                           PT: "em análise por uma pessoa da equipe", EN: "under human review"},
    ApplicationStatus.WITHDRAWN: {ES: "retirada", PT: "retirada", EN: "withdrawn"},
    ApplicationStatus.CLOSED: {ES: "cerrada", PT: "encerrada", EN: "closed"},
}  # fmt: skip
_AND = {ES: "y", PT: "e", EN: "and"}


def join(items: Sequence[str], language: Language) -> str:
    """``a, b y c`` in Spanish, ``a, b e c`` in Portuguese, ``a, b and c`` in English."""
    if len(items) <= 1:
        return "".join(items)
    return f"{', '.join(items[:-1])} {_AND[language]} {items[-1]}"


def pick(labels: Labels, language: Language) -> str:
    """The label in ``language`` (Spanish when a label has no text in it)."""
    return labels.get(language) or labels[ES]
