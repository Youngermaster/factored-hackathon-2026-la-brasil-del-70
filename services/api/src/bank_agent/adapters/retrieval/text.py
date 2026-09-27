"""Language-aware tokenization for es, pt, and en: accent folding, stopwords, and truncation stemming.

Folding (NFKD, combining marks dropped, casefold) makes ``días`` and ``dias`` the same token, and ``cartão`` and
``cartao``. Truncating every token to its first six characters is a light, deterministic stemmer that joins the
inflections Spanish and Portuguese build on one stem (``bloquear``, ``bloqueo``, ``bloqueada`` become ``bloque``).
A change to any list or to the prefix length changes ``TOKENIZER_VERSION``, which invalidates stored indexes.
"""

import re
import unicodedata

from bank_agent.domain.locale import Language

TOKENIZER_VERSION = "fold-stop-trunc6@1"
PREFIX_LENGTH = 6
_TOKEN = re.compile(r"[a-z0-9]+")

_SPANISH = """
a al algo algun alguna algunas alguno algunos ante antes asi aun cada como con contra cual cuales cuando cuanto
cuantos cuantas de del desde donde dos e el ella ellas ello ellos en entre era eran es esa esas ese eso esos esta
estas este esto estos fue fueron ha han hasta hay la las le les lo los mas me mi mis mucho muy nada ni no nos
nosotros o os otra otras otro otros para pero poco por porque puede que quien se sea ser si sin sobre son su sus
tambien te tengo ti tiene tienen todo todos tu tus un una uno unos usted ustedes vos y ya yo mio mia hola favor
quiero quisiera saber necesito puedo podria debo hacer
"""
_PORTUGUESE = """
a ao aos as ate com como da das de dela dele deles do dos e ela elas ele eles em entre era essa essas esse esses
esta estas este estes eu foi foram ha isso isto ja la lhe lhes mais mas me meu meus minha minhas muito na nas nao
nem no nos nossa nosso num numa o os ou para pela pelas pelo pelos por porque pode qual quais quando quanto que
quem se sem ser seu seus si sua suas tambem te tem ter tu tua um uma uns umas voce voces vou ola favor quero
queria saber preciso posso poderia devo fazer
"""
_ENGLISH = """
a about am an and any are as at be been but by can could do does for from had has have how i if in into is it
its me my no not of on or our so than that the their them then there these they this to up was we were what when
where which who why will with would you your hello please want know need
"""

STOPWORDS: dict[Language, frozenset[str]] = {
    Language.ES: frozenset(_SPANISH.split()),
    Language.PT: frozenset(_PORTUGUESE.split()),
    Language.EN: frozenset(_ENGLISH.split()),
}


def fold(text: str) -> str:
    """Casefold and strip accents: ``Días Hábiles`` becomes ``dias habiles``."""
    decomposed = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in decomposed if not unicodedata.combining(character))


def tokenize(text: str, language: Language) -> tuple[str, ...]:
    """Folded word tokens without the language's stopwords, each truncated to ``PREFIX_LENGTH`` characters.

    Single letters are dropped; numbers are kept whole, because a figure is a meaningful query term.
    """
    stopwords = STOPWORDS[language]
    tokens: list[str] = []
    for token in _TOKEN.findall(fold(text)):
        if token in stopwords or (len(token) == 1 and not token.isdigit()):
            continue
        tokens.append(token if token.isdigit() else token[:PREFIX_LENGTH])
    return tuple(tokens)
