"""The deterministic transaction descriptor: what UNDERSTAND extracts from a message when the language model is off.

It combines the same parsers the dispute and account workflows use (``amounts``, ``dates``, ``extraction``): the
best amount and its currency (the account currency when the candidates share one), the first date expression with
its interpretations kept inside ``earliest``..``today``, a merchant phrase, the channel, and a card ending.
``bank-ml`` builds the resolver's training and evaluation descriptors with it, so the learned resolver sees the
descriptors the engine produces rather than idealized ones.
"""

from datetime import date

from bank_agent.application.understanding import amounts, dates, extraction
from bank_agent.domain.base import UntrustedText
from bank_agent.domain.intelligence import TransactionDescriptor
from bank_agent.domain.money import Currency


def deterministic_descriptor(
    text: str, today: date, currencies: frozenset[Currency], earliest: date | None = None
) -> TransactionDescriptor:
    mention = amounts.best_amount(text)
    found = dates.resolve_dates(text, today)
    interpretations = found.interpretations if found is not None else ()
    if earliest is not None:
        interpretations = dates.narrow(interpretations, earliest, today)
    merchant = extraction.merchant_phrase(text)
    return TransactionDescriptor(
        amount=mention.amount if mention is not None else None,
        currency_hint=amounts.resolve_currency(mention, currencies) if mention is not None else None,
        merchant_text=UntrustedText(merchant[:150]) if merchant else None,
        date_expression=UntrustedText(found.expression[:100]) if found is not None else None,
        date_interpretations=interpretations[:4],
        channel_hint=extraction.channel(text),
        card_last4_hint=extraction.card_last4(text),
    )
