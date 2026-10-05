"""Templates shared by every workflow: language question, greeting, routing, scope, pauses, and handoffs."""

from bank_agent.domain.locale import Language

ES, PT, EN = Language.ES, Language.PT, Language.EN

COMMON: dict[str, dict[Language, str]] = {
    "common.language_question": {
        ES: "¿En qué idioma prefieres que te atienda: español o portugués?",
        PT: "Em qual idioma você prefere ser atendido: espanhol ou português?",
        EN: "Which language do you prefer: Spanish or Portuguese?",
    },
    "common.greeting": {
        ES: "Hola. Puedo ayudarte con {capabilities}. ¿En qué te ayudo?",
        PT: "Olá. Posso ajudar com {capabilities}. Como posso ajudar?",
        EN: "Hello. I can help with {capabilities}. How can I help?",
    },
    "common.clarify_intent": {
        ES: "No entendí bien tu solicitud. Puedo ayudarte con {capabilities}. ¿Qué necesitas?",
        PT: "Não entendi bem o seu pedido. Posso ajudar com {capabilities}. Do que você precisa?",
        EN: "I did not understand your request. I can help with {capabilities}. What do you need?",
    },
    "common.clarify_workflow": {
        ES: "Para ayudarte mejor: ¿tu consulta es sobre {first} o sobre {second}?",
        PT: "Para ajudar melhor: o seu pedido é sobre {first} ou sobre {second}?",
        EN: "To help you better: is your request about {first} or about {second}?",
    },
    "common.out_of_scope": {
        ES: "Eso no lo puedo hacer aquí. Puedo ayudarte con {capabilities}. Si prefieres, te comunico con una "
        "persona del equipo.",
        PT: "Isso eu não consigo fazer aqui. Posso ajudar com {capabilities}. Se preferir, transfiro você para uma "
        "pessoa da equipe.",
        EN: "I cannot do that here. I can help with {capabilities}. If you prefer, I can connect you with a person "
        "from the team.",
    },
    "common.switch_confirm": {
        ES: "Todavía tenemos pendiente {pending}. ¿Quieres dejarlo y pasar a {target}? Responde sí o no.",
        PT: "Ainda temos pendente {pending}. Quer deixar isso e passar para {target}? Responda sim ou não.",
        EN: "We still have {pending} pending. Do you want to leave it and move to {target}? Answer yes or no.",
    },
    "common.switch_declined": {
        ES: "De acuerdo, seguimos con {pending}.",
        PT: "Certo, seguimos com {pending}.",
        EN: "All right, we continue with {pending}.",
    },
    "common.escalated": {
        ES: "Voy a pasar tu conversación a una persona del equipo, que te contactará a más tardar el {due}. "
        "Le comparto lo que ya verificamos para que no tengas que repetirlo.",
        PT: "Vou transferir a sua conversa para uma pessoa da equipe, que vai entrar em contato até {due}. "
        "Compartilho o que já verificamos para você não precisar repetir.",
        EN: "I am passing your conversation to a person from the team, who will contact you by {due}. "
        "I am sharing what we already verified so you do not have to repeat it.",
    },
    "common.escalated_already": {
        ES: "Tu solicitud ya está con una persona del equipo, que te contactará a más tardar el {due}.",
        PT: "O seu pedido já está com uma pessoa da equipe, que vai entrar em contato até {due}.",
        EN: "Your request is already with a person from the team, who will contact you by {due}.",
    },
    "common.refused": {
        ES: "No encontré ese registro entre tus productos. Solo puedo ayudarte con tus propios productos y "
        "transacciones.",
        PT: "Não encontrei esse registro entre os seus produtos. Só posso ajudar com os seus próprios produtos e "
        "transações.",
        EN: "I did not find that record among your products. I can only help with your own products and transactions.",
    },
    "common.refused_third_party": {
        ES: "No puedo atender solicitudes sobre los productos o los datos de otra persona u otro cliente. Solo "
        "puedo ayudarte con tus propios productos.",
        PT: "Não posso atender pedidos sobre os produtos ou os dados de outra pessoa ou de outro cliente. Só posso "
        "ajudar com os seus próprios produtos.",
        EN: "I cannot handle requests about another person's or another customer's products or data. I can only "
        "help with your own products.",
    },
    "common.refused_step_up_notice": {
        ES: "Por seguridad, debido a esta solicitud, si quieres seguir con tus propios productos te pediré una "
        "verificación reforzada de tu identidad.",
        PT: "Por segurança, devido a este pedido, se quiser seguir com os seus próprios produtos vou pedir uma "
        "verificação reforçada da sua identidade.",
        EN: "For security, because of this request, if you want to continue with your own products I will ask for "
        "a stronger verification of your identity.",
    },
    "common.refused_review_notice": {
        ES: "Por seguridad, debido a esta solicitud, si necesitas algo más en esta sesión te atenderá una "
        "persona del equipo.",
        PT: "Por segurança, devido a este pedido, se precisar de mais alguma coisa nesta sessão, uma pessoa da "
        "equipe vai atender você.",
        EN: "For security, because of this request, if you need anything else in this session a person from "
        "the team will assist you.",
    },
    "common.off_topic": {
        ES: "Lo siento, ese tema está fuera de lo que puedo atender. Solo te ayudo con tus productos de este "
        "banco: {capabilities}. ¿Te ayudo con alguno de esos temas?",
        PT: "Desculpe, esse assunto está fora do que posso atender. Só ajudo com os seus produtos deste banco: "
        "{capabilities}. Posso ajudar com algum desses assuntos?",
        EN: "Sorry, that topic is outside what I can handle. I only help with your products at this bank: "
        "{capabilities}. Can I help with one of those topics?",
    },
    "common.auth_required": {
        ES: "Tu sesión venció. Para continuar necesito que verifiques tu identidad de nuevo; después retomamos "
        "donde íbamos.",
        PT: "A sua sessão expirou. Para continuar, preciso que você verifique a sua identidade de novo; depois "
        "retomamos de onde paramos.",
        EN: "Your session expired. To continue, please verify your identity again; then we pick up where we left off.",
    },
    "common.limited_service": {
        ES: "En este momento funciono en modo limitado: te respondo con mensajes estándar y, si tu caso lo necesita, "
        "te comunico con una persona del equipo.",
        PT: "No momento estou funcionando em modo limitado: respondo com mensagens padrão e, se o seu caso precisar, "
        "encaminho você para uma pessoa da equipe.",
        EN: "I am working in a limited mode right now: I answer with standard messages and, if your case needs it, "
        "I connect you with a person on the team.",
    },
    "common.unsafe_blocked": {
        ES: "No puedo darte esa respuesta en este momento. Si lo necesitas, te comunico con una persona del equipo.",
        PT: "Não posso dar essa resposta no momento. Se precisar, encaminho você para uma pessoa da equipe.",
        EN: "I cannot give you that answer right now. If you need it, I can connect you with a person on the team.",
    },
    "common.resume": {
        ES: "Gracias por verificar tu identidad. Retomemos donde íbamos.",
        PT: "Obrigado por verificar a sua identidade. Vamos retomar de onde paramos.",
        EN: "Thank you for verifying your identity. Let us pick up where we left off.",
    },
    "common.step_up_required": {
        ES: "Para hacer esto necesito una verificación reforzada de tu identidad. Complétala y escríbeme para "
        "continuar.",
        PT: "Para fazer isso, preciso de uma verificação reforçada da sua identidade. Conclua e me escreva para "
        "continuar.",
        EN: "To do this I need a stronger verification of your identity. Complete it and write to me to continue.",
    },
    "common.step_up_required_risk": {
        ES: "Por seguridad, debido a lo que se pidió en esta conversación, necesito una verificación reforzada de "
        "tu identidad antes de continuar. Complétala y escríbeme para seguir.",
        PT: "Por segurança, devido ao que foi pedido nesta conversa, preciso de uma verificação reforçada da sua "
        "identidade antes de continuar. Conclua e me escreva para seguir.",
        EN: "For security, because of what was asked in this conversation, I need a stronger verification of your "
        "identity before continuing. Complete it and write to me to continue.",
    },
    "common.informational_answer": {
        ES: "Esto es lo que dice la política que aplica a tu consulta:",
        PT: "Isto é o que diz a política que se aplica ao seu pedido:",
        EN: "This is what the applicable policy says:",
    },
    "common.informational_abstain": {
        ES: "No encontré una regla de la política que responda tu pregunta con seguridad. Si quieres, te comunico "
        "con una persona del equipo.",
        PT: "Não encontrei uma regra da política que responda à sua pergunta com segurança. Se quiser, transfiro "
        "você para uma pessoa da equipe.",
        EN: "I did not find a policy rule that answers your question reliably. If you want, I can connect you "
        "with a person from the team.",
    },
    "common.nothing_recorded": {
        ES: "De acuerdo, no registré nada. ¿Hay algo más en lo que te ayude?",
        PT: "Certo, não registrei nada. Posso ajudar com mais alguma coisa?",
        EN: "All right, nothing was recorded. Can I help with anything else?",
    },
    "common.confirm_again": {
        ES: "No te entendí. Responde sí para confirmar o no para cancelar.",
        PT: "Não entendi. Responda sim para confirmar ou não para cancelar.",
        EN: "I did not understand. Answer yes to confirm or no to cancel.",
    },
}
