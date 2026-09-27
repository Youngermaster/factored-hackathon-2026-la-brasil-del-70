"""Deterministic customer descriptions of a known transaction, in Spanish (by country) and Portuguese.

Each description gives a random subset of clues, never none of amount, merchant, and date: the amount exact,
rounded ("como 1,300 pesos"), or in slang ("15 lucas", "15 mil pesos"); the merchant exact, misspelled (one
letter), or partial (one distinctive word); the date relative ("ayer", "hace 4 días"), as a weekday, or explicit
("el 3 de mayo", "03/05", which can be ambiguous); and sometimes a channel hint. The ground truth is the transaction
the text was written from. Randomness comes from ``rng("describe", query_id)``.
"""

import random
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from bank_agent.domain.locale import Country
from bank_agent.domain.money import Currency
from bank_agent.domain.transaction import Transaction, TransactionChannel

MONTHS_ES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre")  # fmt: skip
MONTHS_PT = ("janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro",
             "novembro", "dezembro")  # fmt: skip
WEEKDAYS_ES = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
WEEKDAYS_PT = ("segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo")
DISPUTE_ES = (
    "No reconozco un cargo {amount} {merchant} {date}",
    "Me cobraron {amount} {merchant} {date} y no fui yo",
    "Quiero reclamar una compra {merchant} {date} {amount}",
    "Hay un cobro raro {date} {amount} {merchant}, ayúdenme",
)
DISPUTE_AR = (
    "Che, tengo un cargo {amount} {merchant} {date} que no hice",
    "No reconozco lo que me cobraron {merchant} {date} {amount}",
)
DISPUTE_PT = (
    "Não reconheço uma cobrança {amount} {merchant} {date}",
    "Me cobraram {amount} {merchant} {date} e não fui eu",
    "Quero contestar uma compra {merchant} {date} {amount}",
)
PAYMENT_ES = (
    "¿Ya se acreditó la transferencia {amount} que hice {date}?",
    "Quiero saber si llegó mi pago {amount} {date}",
    "¿Se reflejó el pago {amount} {date}?",
)
PAYMENT_PT = ("Minha transferência {amount} {date} já caiu?", "Queria saber se o pagamento {amount} {date} entrou")
CHANNELS_ES = {
    TransactionChannel.ATM: "en el cajero",
    TransactionChannel.APP: "por la app",
    TransactionChannel.WEB: "por internet",
}
CHANNELS_PT = {
    TransactionChannel.ATM: "no caixa eletrônico",
    TransactionChannel.APP: "pelo aplicativo",
    TransactionChannel.WEB: "pela internet",
}


@dataclass(frozen=True)
class Description:
    text: str
    clues: dict[str, str]


def _number(value: Decimal, country: Country | None, decimals: bool) -> str:
    quantized = value.quantize(Decimal("0.01") if decimals else Decimal(1), rounding=ROUND_HALF_UP)
    text = f"{quantized:,.2f}" if decimals else f"{quantized:,.0f}"
    if country is Country.MX:
        return text
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


def amount_phrase(txn: Transaction, country: Country, language: str, style: str) -> str:
    value = txn.amount.amount
    usd = txn.amount.currency is Currency.USD
    unit = "dólares" if usd else "pesos"
    styled = None if language == "es" else Country.CO
    if style == "slang" and value >= 1000 and not usd:
        thousands = int((value / 1000).quantize(Decimal(1), rounding=ROUND_HALF_UP))
        word = "lucas" if country in {Country.AR, Country.CO} and language == "es" else "mil pesos"
        return f"de {thousands} {word}"
    if style == "rounded":
        step = Decimal(100) if value >= 1000 else Decimal(10)
        rounded = (value / step).quantize(Decimal(1), rounding=ROUND_HALF_UP) * step
        prefix = "de como" if language == "es" else "de uns"
        return f"{prefix} {_number(rounded, styled or country, False)} {unit}"
    decimals = value != value.to_integral_value()
    if usd:
        return f"de US$ {_number(value, Country.MX, decimals)}"
    return f"de ${_number(value, styled or country, decimals)}"


def misspell(name: str, generator: random.Random) -> str:
    words = name.split()
    longest = max(range(len(words)), key=lambda i: len(words[i]))
    word = words[longest]
    if len(word) > 4:
        cut = generator.randrange(1, len(word) - 1)
        words[longest] = word[:cut] + word[cut + 1 :]
    return " ".join(words)


def merchant_phrase(name: str, language: str, style: str, generator: random.Random) -> str:
    if style == "misspelled":
        name = misspell(name, generator)
    elif style == "partial":
        name = max(name.split(), key=len)
    return f"en {name}" if language == "es" else f"na {name}"


def date_phrase(day: date, today: date, language: str, style: str) -> str:
    back = (today - day).days
    if style == "relative":
        if language == "es":
            return {0: "hoy", 1: "ayer", 2: "anteayer"}[back]
        return {0: "hoje", 1: "ontem", 2: "anteontem"}[back]
    if style == "days_ago":
        return f"hace {back} días" if language == "es" else f"há {back} dias"
    if style == "weekday":
        if language == "es":
            return f"el {WEEKDAYS_ES[day.weekday()]}"
        return f"{'no' if day.weekday() >= 5 else 'na'} {WEEKDAYS_PT[day.weekday()]}"
    if style == "numeric":
        return f"el {day.day:02d}/{day.month:02d}" if language == "es" else f"no dia {day.day:02d}/{day.month:02d}"
    month = MONTHS_ES[day.month - 1] if language == "es" else MONTHS_PT[day.month - 1]
    return f"el {day.day} de {month}" if language == "es" else f"no dia {day.day} de {month}"


def _date_styles(back: int) -> list[str]:
    styles = ["explicit", "numeric", "none"]
    if back <= 2:
        styles.append("relative")
    if 2 <= back <= 10:
        styles.append("days_ago")
    if 1 <= back <= 6:
        styles.append("weekday")
    return styles


def describe(
    txn: Transaction, *, use: str, country: Country, language: str, today: date, day: date, generator: random.Random
) -> Description:
    """A description of ``txn`` (occurred on local ``day``) as told on local ``today``."""
    while True:
        amount_style = generator.choice(("exact", "exact", "rounded", "slang", "none"))
        merchant_style = generator.choice(("exact", "misspelled", "partial", "none")) if txn.merchant_name else "none"
        date_style = generator.choice(_date_styles((today - day).days))
        if {amount_style, merchant_style, date_style} != {"none"}:
            break
    parts = {
        "amount": amount_phrase(txn, country, language, amount_style) if amount_style != "none" else "",
        "merchant": merchant_phrase(txn.merchant_name or "", language, merchant_style, generator)
        if merchant_style != "none"
        else "",
        "date": date_phrase(day, today, language, date_style) if date_style != "none" else "",
    }
    templates: tuple[str, ...]
    if use == "payment_lookup":
        templates = PAYMENT_ES if language == "es" else PAYMENT_PT
    elif language == "pt":
        templates = DISPUTE_PT
    else:
        templates = DISPUTE_ES + (DISPUTE_AR if country is Country.AR else ())
    text = generator.choice(templates).format(**parts)
    channels = CHANNELS_ES if language == "es" else CHANNELS_PT
    channel_style = "none"
    if txn.channel in channels and generator.random() < 0.15:
        text = f"{text} {channels[txn.channel]}"
        channel_style = txn.channel.value
    clues = {"amount": amount_style, "merchant": merchant_style, "date": date_style, "channel": channel_style}
    return Description(" ".join(text.split()).replace(" ,", ",").replace(" ?", "?"), clues)
