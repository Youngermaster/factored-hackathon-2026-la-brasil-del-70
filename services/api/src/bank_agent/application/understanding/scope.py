"""``scope:lexicon@1``: whether a message the router could not place is about banking at all (es, pt, en).

A closed-domain lexicon, deterministic and model-free. The engine asks it only when the router is unsure (below its
threshold, or ``greeting_or_other``), before asking which workflow the request belongs to:

- ``COURTESY``: only greetings, thanks, yes or no, a language name, or bare numbers ("hola", "buenos días",
  "obrigado").
- ``SERVICE``: a bank-side request the assistant never handles (``SCOPE-ALL-2``): changing personal data
  ("actualiza mi correo electrónico") or tax advice ("¿cómo declaro mis impuestos?").
- ``BANKING``: a banking word (account, card, balance, charge, loan, money), or a vague call for help with no
  unrelated topic ("tengo un problema", "necesito ayuda"). Such a message is plausibly banking and keeps the
  clarifying question.
- ``OFF_TOPIC``: anything else ("¿Quién es mejor, CR7 o Messi?", "¿va a llover mañana?", "dame una receta").

A banking word always wins over an unrelated topic, so "¿puedo pagar el partido con mi tarjeta?" stays banking.
"""

import re
from enum import StrEnum

from bank_agent.application.understanding.text import fold, words

SCOPE_DETECTOR = "scope:lexicon@1"


class Scope(StrEnum):
    COURTESY = "courtesy"
    SERVICE = "service"
    BANKING = "banking"
    OFF_TOPIC = "off_topic"


COURTESY_WORDS = frozenset({
    "hola", "holi", "ola", "oi", "buenas", "buenos", "buen", "bom", "boa", "dia", "dias", "tardes", "tarde",
    "noches", "noite", "noites", "que", "tal", "como", "estas", "esta", "vai", "tudo", "bem", "bien", "gracias",
    "muchas", "muchisimas", "obrigado", "obrigada", "muito", "valeu", "ok", "okay", "vale", "listo", "perfecto",
    "claro", "si", "sim", "no", "nao", "por", "favor", "adios", "chao", "chau", "tchau", "hasta", "luego", "hello",
    "hi", "hey", "thanks", "thank", "you", "yes", "espanol", "portugues", "spanish", "portuguese", "ingles",
    "english", "senor", "senora", "senhor", "senhora", "a", "o", "e", "y", "de",
})  # fmt: skip
"""Words that alone make a greeting, thanks, a bare yes or no, or a language answer."""
_SERVICE = re.compile(
    r"\b(?:actualiz|cambi|modific|corrig|atualiz|alter|mud|troc|update|change)\w* (?:\w+ ){0,3}"
    r"(?:correo|e-?mail|mail|telefono|celular|numero de (?:telefono|celular)|direccion|domicilio|endereco|"
    r"datos personales|dados pessoais|dados cadastrais|nombre|nome|apellido|sobrenome|phone|address)\b"
    r"|\b(?:impuestos?|impostos?|tributari\w*|fiscal\w*|declaracion de renta|imposto de renda|declarar (?:la )?renta|"
    r"taxes|tax return)\b"
)
_BANKING = re.compile(
    r"\b(?:cuentas?|contas?|accounts?|tarjetas?|cartao|cartoes|cards?|saldos?|balance|pagos?|pagar\w*|pague\w*|"
    r"pagamentos?|pagu\w*|pay\w*|transferenci\w*|transfer\w*|deposit\w*|retir\w*|saque\w*|sacar|bancos?|bancari\w*|"
    r"bank\w*|creditos?|credit\w*|debitos?|debit\w*|prestamos?|emprestimos?|loans?|hipoteca\w*|financiamient\w*|"
    r"financiament\w*|cargos?|cobro\w*|cobra\w*|charge\w*|compras?|purchase\w*|dinero|plata|dinheiro|money|pesos?|"
    r"reais|dolar\w*|reclam\w*|contest\w*|disputa\w*|dispute\w*|aclaracion\w*|bloque\w*|bloquei\w*|desbloque\w*|"
    r"block\w*|clave|contrasena|senha|pin|nip|cajeros?|caixa eletronico|atm|movimient\w*|movimentac\w*|extractos?|"
    r"extratos?|statements?|deudas?|dividas?|debts?|tasas?|taxas?|interes\w*|juros|cuotas?|parcelas?|facturas?|"
    r"faturas?|boletos?|pix|cheques?|limites?|cupo|sobregiro|ahorros?|poupanca|nomina|sueldo|salario|comision\w*|"
    r"tarifas?|fees?|apps?|aplicacion|aplicativo|transacci\w*|transac\w*|solicitud\w*|solicitac\w*|elegib\w*|"
    r"aprob\w*|aprov\w*|vencimiento|vence|fraude\w*|robo|robaron|roubo|roubaram|perdi|visa|mastercard|sucursal|"
    r"agencia|caso|casos|seguro)\b"
)
_HELP = re.compile(
    r"\b(?:problemas?|ayuda\w*|ayudar\w*|ajuda\w*|ajudar\w*|help|dudas?|duvidas?|consultas?|preguntas?|perguntas?|"
    r"inconvenientes?|errores?|erros?|falla\w*|falha\w*|no funciona|nao funciona|issue|queja\w*|reclamac\w*|"
    r"asesor\w*|atendente|persona|pessoa|humano|agente)\b"
)
_UNRELATED = re.compile(
    r"\b(?:futbol|futebol|football|soccer|partidos?|jogos?|goles?|gols?|messi|cr7|cristiano|ronaldo|neymar|mundial|"
    r"copa|liga|champions|deportes?|esportes?|sports?|clima|weather|llover|lluvia|chover|chuva|rain|temperatura|"
    r"recetas?|receitas? de|recipes?|cocinar|cozinhar|cook\w*|peliculas?|filmes?|movies?|series|musica|canciones?|"
    r"songs?|presidente|president|elecciones|eleicoes|elections?|gobierno|governo|politic[ao]s? (?:de|do|del|da) "
    r"(?:pais|gobierno|governo)|chistes?|piadas?|jokes?|poemas?|poems?|horoscopo|capital de|quien es mejor|"
    r"quem e melhor|who is better)\b"
)


def classify_scope(text: str) -> Scope:
    """The scope of ``text`` (see the module docstring). Pure and deterministic."""
    tokens = words(text)
    if all(token in COURTESY_WORDS or token.isdigit() for token in tokens):
        return Scope.COURTESY
    folded = fold(text)
    if _SERVICE.search(folded):
        return Scope.SERVICE
    if _BANKING.search(folded):
        return Scope.BANKING
    if _HELP.search(folded) and not _UNRELATED.search(folded):
        return Scope.BANKING
    return Scope.OFF_TOPIC
