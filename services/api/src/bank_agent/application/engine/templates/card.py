"""Card support templates in Spanish, Portuguese, and English (console preview)."""

from bank_agent.domain.locale import Language

ES, PT, EN = Language.ES, Language.PT, Language.EN

CARD: dict[str, dict[Language, str]] = {
    "card.clarify_options": {
        ES: "Tienes varias tarjetas. ¿Sobre cuál me consultas?\n{options}",
        PT: "Você tem vários cartões. Sobre qual deles é o seu pedido?\n{options}",
        EN: "You have several cards. Which one is your request about?\n{options}",
    },
    "card.option": {ES: "{n}) {type} {card}", PT: "{n}) {type} {card}", EN: "{n}) {type} {card}"},
    "card.no_cards": {
        ES: "No encontré tarjetas a tu nombre.",
        PT: "Não encontrei cartões em seu nome.",
        EN: "I found no cards in your name.",
    },
    "card.status": {
        ES: "Tu {type} {card} está {status}.",
        PT: "O seu {type} {card} está {status}.",
        EN: "Your {type} {card} is {status}.",
    },
    "card.status_with_expiry": {
        ES: "Tu {type} {card} está {status} y vence el {expires}.",
        PT: "O seu {type} {card} está {status} e vence em {expires}.",
        EN: "Your {type} {card} is {status} and expires on {expires}.",
    },
    "card.declined": {
        ES: "Compras rechazadas recientes (los registros no indican el motivo):\n{items}",
        PT: "Compras recusadas recentes (os registros não indicam o motivo):\n{items}",
        EN: "Recent declined purchases (the records do not state the reason):\n{items}",
    },
    "card.declined_item": {
        ES: "{date}, {merchant}, {amount}",
        PT: "{date}, {merchant}, {amount}",
        EN: "{date}, {merchant}, {amount}",
    },
    "card.confirm_block": {
        ES: "Voy a bloquear tu {type} {card}. El bloqueo es inmediato y la tarjeta dejará de funcionar. "
        "¿Confirmas? Responde sí o no.",
        PT: "Vou bloquear o seu {type} {card}. O bloqueio é imediato e o cartão deixará de funcionar. "
        "Confirma? Responda sim ou não.",
        EN: "I will block your {type} {card}. The block is immediate and the card will stop working. Do you "
        "confirm? Answer yes or no.",
    },
    "card.offer_block_first": {
        ES: "Antes de pasar tu solicitud a una persona del equipo, te recomiendo bloquear tu {type} {card} para "
        "que nadie pueda usarla. ¿Quieres que la bloquee? Responde sí o no.",
        PT: "Antes de passar o seu pedido para uma pessoa da equipe, recomendo bloquear o seu {type} {card} para "
        "que ninguém possa usá-lo. Quer que eu bloqueie? Responda sim ou não.",
        EN: "Before I pass your request to a person from the team, I recommend blocking your {type} {card} so "
        "nobody can use it. Do you want me to block it? Answer yes or no.",
    },
    "card.blocked": {
        ES: "Listo: bloqueamos tu {type} {card} y lo comprobamos en los registros.",
        PT: "Pronto: bloqueamos o seu {type} {card} e conferimos nos registros.",
        EN: "Done: we blocked your {type} {card} and checked it in the records.",
    },
    "card.not_blockable": {
        ES: "No puedo bloquear tu {type} {card} desde aquí.",
        PT: "Não posso bloquear o seu {type} {card} por aqui.",
        EN: "I cannot block your {type} {card} from here.",
    },
    "card.anything_else": {
        ES: "¿Hay algo más en lo que te ayude con tus tarjetas?",
        PT: "Posso ajudar com mais alguma coisa sobre os seus cartões?",
        EN: "Can I help with anything else about your cards?",
    },
}
