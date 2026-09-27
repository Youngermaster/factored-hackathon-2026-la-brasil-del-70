"""Credit templates in Spanish, Portuguese, and English (console preview).

No credit template contains approval wording, even negated (the stems of ``policy.lexicon``), states an eligibility
outcome of its own, or carries a figure: outcomes come only from the rendered ``EligibilityView`` and figures only
from the catalog entry and the customer's request.
"""

from bank_agent.domain.locale import Language

ES, PT, EN = Language.ES, Language.PT, Language.EN

CREDIT: dict[str, dict[Language, str]] = {
    "credit.product_list": {
        ES: "Estos son los productos del catálogo sintético de crédito para tu país:",
        PT: "Estes são os produtos do catálogo sintético de crédito para o seu país:",
        EN: "These are the products of the synthetic credit catalog for your country:",
    },
    "credit.product_line": {
        ES: "- {name}: de {min} a {max}",
        PT: "- {name}: de {min} a {max}",
        EN: "- {name}: from {min} to {max}",
    },
    "credit.product_line_info_only": {
        ES: "- {name}: de {min} a {max} (solo información)",
        PT: "- {name}: de {min} a {max} (somente informação)",
        EN: "- {name}: from {min} to {max} (information only)",
    },
    "credit.ask_which_product": {
        ES: "¿Sobre cuál quieres más detalle?",
        PT: "Sobre qual deles você quer mais detalhes?",
        EN: "Which one do you want more detail about?",
    },
    "credit.product_detail": {
        ES: "{name}: montos de {min} a {max}; plazos de {min_term} a {max_term} meses; tasa anual de {min_rate} a "
        "{max_rate}.",
        PT: "{name}: valores de {min} a {max}; prazos de {min_term} a {max_term} meses; taxa anual de {min_rate} a "
        "{max_rate}.",
        EN: "{name}: amounts from {min} to {max}; terms from {min_term} to {max_term} months; annual rate from "
        "{min_rate} to {max_rate}.",
    },
    "credit.product_detail_card": {
        ES: "{name}: límites de {min} a {max}; tasa anual de {min_rate} a {max_rate}.",
        PT: "{name}: limites de {min} a {max}; taxa anual de {min_rate} a {max_rate}.",
        EN: "{name}: limits from {min} to {max}; annual rate from {min_rate} to {max_rate}.",
    },
    "credit.offer_guide": {
        ES: "Si quieres una orientación indicativa para este producto, pregúntame por tu elegibilidad y dime el "
        "monto que te interesa.",
        PT: "Se quiser uma orientação indicativa para este produto, pergunte pela sua elegibilidade e diga o valor "
        "que interessa a você.",
        EN: "If you want an indicative guide for this product, ask me about your eligibility and tell me the amount "
        "you are interested in.",
    },
    "credit.mortgage_info_only": {
        ES: "Las hipotecas son solo informativas por este canal: una persona del equipo de crédito revisa cada caso. "
        "Si quieres, pide hablar con una persona.",
        PT: "Os financiamentos imobiliários são somente informativos por este canal: uma pessoa da equipe de crédito "
        "analisa cada caso. Se quiser, peça para falar com uma pessoa.",
        EN: "Mortgages are information only in this channel: a person from the credit team reviews every case. If "
        "you want, ask to talk to a person.",
    },
    "credit.clarify_product": {
        ES: "¿Qué producto te interesa?\n{options}",
        PT: "Qual produto interessa a você?\n{options}",
        EN: "Which product are you interested in?\n{options}",
    },
    "credit.product_option": {ES: "{n}) {name}", PT: "{n}) {name}", EN: "{n}) {name}"},
    "credit.ask_amount": {
        ES: "¿Qué monto te interesa?",
        PT: "Qual valor interessa a você?",
        EN: "What amount are you interested in?",
    },
    "credit.ask_amount_term": {
        ES: "¿Qué monto te interesa y a qué plazo, en meses?",
        PT: "Qual valor interessa a você e em qual prazo, em meses?",
        EN: "What amount are you interested in, and over what term, in months?",
    },
    "credit.ask_term": {
        ES: "¿A qué plazo, en meses?",
        PT: "Em qual prazo, em meses?",
        EN: "Over what term, in months?",
    },
    "credit.eligibility": {ES: "{explanation}", PT: "{explanation}", EN: "{explanation}"},
    "credit.offer_intake": {
        ES: "¿Quieres que registre tu solicitud para que la revise una persona del equipo de crédito? Responde sí "
        "o no.",
        PT: "Quer que eu registre a sua solicitação para que uma pessoa da equipe de crédito a analise? Responda sim "
        "ou não.",
        EN: "Do you want me to record your application for a person from the credit team to review? Answer yes or no.",
    },
    "credit.offer_review": {
        ES: "¿Quieres que una persona del equipo de crédito revise tu caso? Responde sí o no.",
        PT: "Quer que uma pessoa da equipe de crédito analise o seu caso? Responda sim ou não.",
        EN: "Do you want a person from the credit team to review your case? Answer yes or no.",
    },
    "credit.offer_missing_income": {
        ES: "Puedes decirme tu ingreso mensual para darte la orientación de nuevo, o responder sí para que una persona "
        "del equipo de crédito revise tu caso.",
        PT: "Você pode me dizer a sua renda mensal para eu refazer a orientação, ou responder sim para que uma pessoa "
        "da equipe de crédito analise o seu caso.",
        EN: "You can tell me your monthly income so I can give the guide again, or answer yes for a person from the "
        "credit team to review your case.",
    },
    "credit.confirm_intake": {
        ES: "Voy a registrar tu solicitud de {name} por {amount} ({purpose}) para que la revise una persona del "
        "equipo de crédito. En esta conversación no se toma ninguna decisión y no se mueve dinero. ¿Confirmas? "
        "Responde sí o no.",
        PT: "Vou registrar a sua solicitação de {name} de {amount} ({purpose}) para que uma pessoa da equipe de "
        "crédito a analise. Nesta conversa nenhuma decisão é tomada e nenhum dinheiro é movimentado. Confirma? "
        "Responda sim ou não.",
        EN: "I will record your application for a {name} of {amount} ({purpose}) for a person from the credit team to "
        "review. No decision is made and no money moves in this conversation. Do you confirm? Answer yes or no.",
    },
    "credit.term_line": {
        ES: "Plazo solicitado, en meses: {term}.",
        PT: "Prazo solicitado, em meses: {term}.",
        EN: "Requested term, in months: {term}.",
    },
    "credit.intake_recorded": {
        ES: "Listo: registramos tu solicitud {application} para que la revise una persona del equipo de crédito, y lo "
        "comprobamos en los registros. No es una oferta ni una decisión de crédito.",
        PT: "Pronto: registramos a sua solicitação {application} para que uma pessoa da equipe de crédito a analise, "
        "e conferimos nos registros. Não é uma oferta nem uma decisão de crédito.",
        EN: "Done: we recorded your application {application} for a person from the credit team to review, and we "
        "checked it in the records. It is neither an offer nor a credit decision.",
    },
    "credit.intake_not_possible": {
        ES: "No puedo registrar esa solicitud por este medio.",
        PT: "Não consigo registrar essa solicitação por este canal.",
        EN: "I cannot record that application in this channel.",
    },
    "credit.no_decision": {
        ES: "En esta conversación no se toman decisiones de crédito. Puedo darte una orientación indicativa de "
        "elegibilidad con reglas sintéticas o, si prefieres, pedir que una persona del equipo de crédito revise tu "
        "caso.",
        PT: "Nesta conversa não são tomadas decisões de crédito. Posso dar uma orientação indicativa de elegibilidade "
        "com regras sintéticas ou, se preferir, pedir que uma pessoa da equipe de crédito analise o seu caso.",
        EN: "No credit decisions are made in this conversation. I can give you an indicative eligibility guide from "
        "synthetic rules or, if you prefer, ask a person from the credit team to review your case.",
    },
    "credit.status_need_reference": {
        ES: "No encontré una solicitud en esta conversación. Escríbeme el número de tu solicitud o pide hablar con "
        "una persona.",
        PT: "Não encontrei uma solicitação nesta conversa. Escreva o número da sua solicitação ou peça para falar com "
        "uma pessoa.",
        EN: "I found no application in this conversation. Write your application number or ask to talk to a person.",
    },
    "credit.application_status": {
        ES: "Tu solicitud {application} de {name} está {status}.",
        PT: "A sua solicitação {application} de {name} está {status}.",
        EN: "Your application {application} for a {name} is {status}.",
    },
    "credit.status_not_found": {
        ES: "No encontré esa solicitud entre las tuyas.",
        PT: "Não encontrei essa solicitação entre as suas.",
        EN: "I did not find that application among yours.",
    },
    "credit.anything_else": {
        ES: "¿Hay algo más en lo que te ayude con productos de crédito?",
        PT: "Posso ajudar com mais alguma coisa sobre produtos de crédito?",
        EN: "Can I help with anything else about credit products?",
    },
}
