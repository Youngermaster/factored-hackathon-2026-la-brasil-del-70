"""Dispute templates in Spanish, Portuguese, and English (console preview)."""

from bank_agent.domain.locale import Language

ES, PT, EN = Language.ES, Language.PT, Language.EN

DISPUTE: dict[str, dict[Language, str]] = {
    "dispute.ask_details": {
        ES: "Para encontrar la transacción, dime la fecha aproximada, el monto y el comercio.",
        PT: "Para encontrar a transação, me diga a data aproximada, o valor e o estabelecimento.",
        EN: "To find the transaction, tell me the approximate date, the amount, and the merchant.",
    },
    "dispute.clarify_options": {
        ES: "Encontré varias transacciones parecidas. ¿Cuál quieres reclamar?\n{options}",
        PT: "Encontrei várias transações parecidas. Qual você quer contestar?\n{options}",
        EN: "I found several similar transactions. Which one do you want to dispute?\n{options}",
    },
    "dispute.clarify_one": {
        ES: "Encontré esta transacción. ¿Es la que quieres reclamar? Responde sí o no.\n{options}",
        PT: "Encontrei esta transação. É a que você quer contestar? Responda sim ou não.\n{options}",
        EN: "I found this transaction. Is it the one you want to dispute? Answer yes or no.\n{options}",
    },
    "dispute.option": {
        ES: "{n}) {date}, {merchant}, {amount}, tarjeta {card}",
        PT: "{n}) {date}, {merchant}, {amount}, cartão {card}",
        EN: "{n}) {date}, {merchant}, {amount}, card {card}",
    },
    "dispute.clarify_date": {
        ES: "Cuando dices {expression}, ¿te refieres al {first} o al {second}?",
        PT: "Quando você diz {expression}, se refere a {first} ou a {second}?",
        EN: "When you say {expression}, do you mean {first} or {second}?",
    },
    "dispute.ask_reason": {
        ES: "¿Cuál es el motivo? Por ejemplo: no reconoces la compra, un cargo duplicado, un monto distinto, algo "
        "que no recibiste, un retiro en cajero sin efectivo o una suscripción que ya cancelaste.",
        PT: "Qual é o motivo? Por exemplo: você não reconhece a compra, uma cobrança duplicada, um valor diferente, "
        "algo que não recebeu, um saque sem dinheiro ou uma assinatura que já cancelou.",
        EN: "What is the reason? For example: you do not recognize the purchase, a duplicate charge, a different "
        "amount, something not received, an ATM withdrawal without cash, or a cancelled subscription.",
    },
    "dispute.offer_block": {
        ES: "Como no reconoces la compra, puedo bloquear preventivamente tu tarjeta {card} para evitar más "
        "cargos. ¿Quieres que la bloquee? Responde sí o no.",
        PT: "Como você não reconhece a compra, posso bloquear preventivamente o seu cartão {card} para evitar "
        "novas cobranças. Quer que eu bloqueie? Responda sim ou não.",
        EN: "Since you do not recognize the purchase, I can block your card {card} as a precaution. Do you want "
        "me to block it? Answer yes or no.",
    },
    "dispute.confirm": {
        ES: "Voy a registrar una reclamación por la transacción del {date} en {merchant} por {amount} (tarjeta "
        "{card}), motivo: {reason}. Recibirás respuesta a más tardar el {due}. ¿Confirmas? Responde sí o no.",
        PT: "Vou registrar uma contestação da transação de {date} em {merchant} no valor de {amount} (cartão "
        "{card}), motivo: {reason}. Você receberá uma resposta até {due}. Confirma? Responda sim ou não.",
        EN: "I will record a dispute for the transaction of {date} at {merchant} for {amount} (card {card}), "
        "reason: {reason}. You will get an answer by {due}. Do you confirm? Answer yes or no.",
    },
    "dispute.confirm_with_block": {
        ES: "Voy a bloquear tu tarjeta {card} y a registrar una reclamación por la transacción del {date} en "
        "{merchant} por {amount}, motivo: {reason}. Recibirás respuesta a más tardar el {due}. ¿Confirmas? "
        "Responde sí o no.",
        PT: "Vou bloquear o seu cartão {card} e registrar uma contestação da transação de {date} em {merchant} "
        "no valor de {amount}, motivo: {reason}. Você receberá uma resposta até {due}. Confirma? Responda sim "
        "ou não.",
        EN: "I will block your card {card} and record a dispute for the transaction of {date} at {merchant} for "
        "{amount}, reason: {reason}. You will get an answer by {due}. Do you confirm? Answer yes or no.",
    },
    "dispute.case_created": {
        ES: "Listo: registramos tu reclamación con el número de caso {case}. Te responderemos a más tardar el {due}.",
        PT: "Pronto: registramos sua contestação com o número de caso {case}. Vamos responder até {due}.",
        EN: "Done: we registered your dispute with case number {case}. We will answer by {due}.",
    },
    "dispute.case_created_and_blocked": {
        ES: "Listo: bloqueamos tu tarjeta {card} y registramos tu reclamación con el número de caso {case}. Te "
        "responderemos a más tardar el {due}.",
        PT: "Pronto: bloqueamos o seu cartão {card} e registramos sua contestação com o número de caso {case}. "
        "Vamos responder até {due}.",
        EN: "Done: we blocked your card {card} and we registered your dispute with case number {case}. We will "
        "answer by {due}.",
    },
    "dispute.status_one": {
        ES: "Tu caso {case} por {amount} está {status}. La fecha comprometida de respuesta es el {due}.",
        PT: "O seu caso {case} no valor de {amount} está {status}. A data prevista de resposta é {due}.",
        EN: "Your case {case} for {amount} is {status}. The committed answer date is {due}.",
    },
    "dispute.status_many": {
        ES: "Estos son tus casos:\n{items}",
        PT: "Estes são os seus casos:\n{items}",
        EN: "These are your cases:\n{items}",
    },
    "dispute.status_item": {
        ES: "{case}, {amount}: {status}, respuesta a más tardar el {due}",
        PT: "{case}, {amount}: {status}, resposta até {due}",
        EN: "{case}, {amount}: {status}, answer by {due}",
    },
    "dispute.status_none": {
        ES: "No encontré reclamaciones registradas a tu nombre. Si quieres presentar una, cuéntame qué "
        "transacción no reconoces.",
        PT: "Não encontrei contestações registradas em seu nome. Se quiser abrir uma, me diga qual transação "
        "você não reconhece.",
        EN: "I found no disputes in your name. If you want to open one, tell me which transaction you do not "
        "recognize.",
    },
    "dispute.no_refund_guarantee": {
        ES: "Registrar la reclamación no garantiza un reembolso ni un abono provisional: el equipo de revisión lo "
        "decide.",
        PT: "Registrar a contestação não garante reembolso nem crédito provisório: a equipe de revisão decide.",
        EN: "Recording the dispute does not guarantee a refund or a provisional credit: the review team decides.",
    },
    "dispute.existing_case": {
        ES: "Esta transacción ya tiene el caso {case}, que está {status}. La fecha comprometida de respuesta es "
        "el {due}.",
        PT: "Esta transação já tem o caso {case}, que está {status}. A data prevista de resposta é {due}.",
        EN: "This transaction already has case {case}, which is {status}. The committed answer date is {due}.",
    },
    "dispute.denied": {
        ES: "No puedo registrar esta reclamación aquí. Si quieres, te comunico con una persona del equipo.",
        PT: "Não posso registrar esta contestação aqui. Se quiser, transfiro você para uma pessoa da equipe.",
        EN: "I cannot record this dispute here. If you want, I can connect you with a person from the team.",
    },
}
