"""Account inquiry templates in Spanish, Portuguese, and English (console preview).

Every balance line sits below a heading that states the as-of date; totals and counts are in separate sentences so
the verifier can check each amount against its own kind of fact. No template states an opening or closing balance.
"""

from bank_agent.domain.locale import Language

ES, PT, EN = Language.ES, Language.PT, Language.EN

ACCOUNT: dict[str, dict[Language, str]] = {
    "account.balances": {
        ES: "Estos son tus saldos, con datos al {as_of}.",
        PT: "Estes são os seus saldos, com dados de {as_of}.",
        EN: "These are your balances, with data as of {as_of}.",
    },
    "account.balance_item": {
        ES: "- {type} {card}: saldo {balance}",
        PT: "- {type} {card}: saldo {balance}",
        EN: "- {type} {card}: balance {balance}",
    },
    "account.balance_item_credit": {
        ES: "- {type} {card}: saldo {balance}; crédito disponible {available} de un límite de {limit}",
        PT: "- {type} {card}: saldo {balance}; limite disponível {available} de um limite total de {limit}",
        EN: "- {type} {card}: balance {balance}; available credit {available} of a limit of {limit}",
    },
    "account.no_balances": {
        ES: "No encontré productos con saldo a tu nombre.",
        PT: "Não encontrei produtos com saldo em seu nome.",
        EN: "I found no products with a balance in your name.",
    },
    "account.clarify_product": {
        ES: "Tienes varios productos. ¿Sobre cuál me consultas?\n{options}",
        PT: "Você tem vários produtos. Sobre qual deles é o seu pedido?\n{options}",
        EN: "You have several products. Which one is your request about?\n{options}",
    },
    "account.product_option": {ES: "{n}) {type} {card}", PT: "{n}) {type} {card}", EN: "{n}) {type} {card}"},
    "account.clarify_payment": {
        ES: "Encontré varios pagos o transferencias parecidos. ¿Cuál es?\n{options}",
        PT: "Encontrei vários pagamentos ou transferências parecidos. Qual deles é?\n{options}",
        EN: "I found several similar payments or transfers. Which one is it?\n{options}",
    },
    "account.choose_payment": {
        ES: "Estos son tus pagos o transferencias más recientes. ¿Cuál es?\n{options}",
        PT: "Estes são os seus pagamentos ou transferências mais recentes. Qual deles é?\n{options}",
        EN: "These are your most recent payments or transfers. Which one is it?\n{options}",
    },
    "account.payment_option": {
        ES: "{n}) {date}, {payee}, {amount}, {card}",
        PT: "{n}) {date}, {payee}, {amount}, {card}",
        EN: "{n}) {date}, {payee}, {amount}, {card}",
    },
    "account.ask_payment_details": {
        ES: "No encontré ese pago o transferencia. ¿Me das el monto, la fecha aproximada o el destinatario?",
        PT: "Não encontrei esse pagamento ou transferência. Pode me dizer o valor, a data aproximada ou o "
        "destinatário?",
        EN: "I did not find that payment or transfer. Can you give me the amount, the approximate date, or the payee?",
    },
    "account.payment_status": {
        ES: "Estado de {kind} de {amount} del {date} a {payee}: {status}. Datos al {as_of}.",
        PT: "Situação {kind} de {amount} de {date} para {payee}: {status}. Dados de {as_of}.",
        EN: "Status of {kind} of {amount} on {date} to {payee}: {status}. Data as of {as_of}.",
    },
    "account.payment_status_no_payee": {
        ES: "Estado de {kind} de {amount} del {date}: {status}. Datos al {as_of}.",
        PT: "Situação {kind} de {amount} de {date}: {status}. Dados de {as_of}.",
        EN: "Status of {kind} of {amount} on {date}: {status}. Data as of {as_of}.",
    },
    "account.ask_period": {
        ES: "¿De qué periodo quieres el resumen? Por ejemplo: el mes pasado, mayo o la semana pasada.",
        PT: "De qual período você quer o resumo? Por exemplo: o mês passado, maio ou a semana passada.",
        EN: "Which period do you want the summary for? For example: last month, May, or last week.",
    },
    "account.period_too_long": {
        ES: "Ese periodo es más largo de lo que puedo resumir. ¿Me indicas uno más corto?",
        PT: "Esse período é mais longo do que consigo resumir. Pode indicar um mais curto?",
        EN: "That period is longer than I can summarize. Can you give me a shorter one?",
    },
    "account.statement": {
        ES: "Resumen de {of_type} {card} del {start} al {end}, con datos al {as_of}. Operaciones en el periodo: "
        "{count}.",
        PT: "Resumo {of_type} {card} de {start} a {end}, com dados de {as_of}. Operações no período: {count}.",
        EN: "Summary of {of_type} {card} from {start} to {end}, with data as of {as_of}. Operations in the "
        "period: {count}.",
    },
    "account.statement_totals": {
        ES: "Totales en {currency}: cargos {debits}; abonos {credits}.",
        PT: "Totais em {currency}: débitos {debits}; créditos {credits}.",
        EN: "Totals in {currency}: debits {debits}; credits {credits}.",
    },
    "account.statement_other": {
        ES: "Sin clasificar como cargo o abono: {unclassified}. Pendientes, rechazadas o revertidas: {unsettled}.",
        PT: "Sem classificação como débito ou crédito: {unclassified}. Pendentes, recusadas ou estornadas: "
        "{unsettled}.",
        EN: "Not classified as a debit or a credit: {unclassified}. Pending, declined, or reversed: {unsettled}.",
    },
    "account.statement_empty": {
        ES: "No hay operaciones de {of_type} {card} del {start} al {end}, con datos al {as_of}.",
        PT: "Não há operações {of_type} {card} de {start} a {end}, com dados de {as_of}.",
        EN: "There are no operations on {of_type} {card} from {start} to {end}, with data as of {as_of}.",
    },
    "account.anything_else": {
        ES: "¿Hay algo más en lo que te ayude con tus cuentas?",
        PT: "Posso ajudar com mais alguma coisa sobre as suas contas?",
        EN: "Can I help with anything else about your accounts?",
    },
    "common.unsupported_in_workflow": {
        ES: "Eso no lo puedo hacer en esta conversación. Si quieres, te comunico con una persona del equipo.",
        PT: "Isso eu não consigo fazer nesta conversa. Se quiser, transfiro você para uma pessoa da equipe.",
        EN: "I cannot do that in this conversation. If you want, I can connect you with a person from the team.",
    },
}
