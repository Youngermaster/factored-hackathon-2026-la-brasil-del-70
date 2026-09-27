"""Candidate features for the transaction resolver, shared by training (``bank-ml``) and serving (``resolver:lgbm``).

One row per candidate, in ``FEATURE_NAMES`` order. A clue the customer did not give is encoded as ``-1`` (never
NaN), so the tree evaluator needs no missing-value handling beyond LightGBM's defaults. Dates compare in the time
zone of ``now``, which the engine passes in the customer's zone, as in ``resolver:rules@1``. ``FEATURES_ID`` names
this exact behavior; an artifact records it and the adapter refuses another.

``plausible`` is the evidence gate: a candidate is ranked only when it agrees with at least one clue the customer
gave (amount within 5%, merchant similarity at least 0.7, date within two days of an interpretation, channel, or
category). The learned ranker orders plausible candidates; the gate keeps an unrelated lone candidate from being
auto-selected, like the rules baseline's minimum score.
"""

import math
import re
from collections import Counter
from collections.abc import Sequence
from datetime import date, datetime
from decimal import Decimal

from rapidfuzz import fuzz

from bank_agent.application.understanding.text import fold, words
from bank_agent.domain.intelligence import DateRange, TransactionDescriptor
from bank_agent.domain.transaction import Transaction, TransactionCategory

FEATURES_ID = "resolver_features@1"
FEATURE_NAMES = (
    "amount_given",
    "amount_log_abs_diff",
    "amount_rel_diff",
    "currency_match",
    "amount_closeness_rank",
    "date_given",
    "date_distance_days",
    "date_ambiguous",
    "merchant_given",
    "merchant_similarity",
    "category_match",
    "channel_match",
    "recency_days",
    "recency_rank",
    "same_day_count",
    "candidate_count",
)
UNKNOWN = -1.0
MAX_REL_DIFF = 10.0
MAX_DATE_DISTANCE = 60.0
AMOUNT_AGREES = 0.05
MERCHANT_AGREES = 0.7
DATE_AGREES = 2.0

_CATEGORY_WORDS: tuple[tuple[TransactionCategory, str], ...] = (
    (TransactionCategory.FOOD, r"restaurante|comida|super\b|supermercado|mercado|almuerzo|cena|cafe|padaria|lanche"),
    (TransactionCategory.TRANSPORT, r"uber|taxi|gasolin|nafta|combustib|combustiv|posto|estacion de servicio|peaje"),
    (TransactionCategory.ENTERTAINMENT, r"\bcine|cinema|concierto|show|teatro|streaming|musica|spotify|netflix"),
    (TransactionCategory.HEALTH, r"farmacia|drogaria|clinica|medic|laboratorio|optica|hospital|consulta"),
    (TransactionCategory.SERVICES, r"telefon|celular|internet|cable|\bluz\b|\bagua\b|servicios|plano|conta de luz"),
    (TransactionCategory.OTHER, r"boutique|ropa|roupa|ferreteria|centro comercial|shopping"),
)


def category_hint(descriptor: TransactionDescriptor) -> TransactionCategory | None:
    """The category the merchant words point at, or ``None``."""
    if not descriptor.merchant_text:
        return None
    folded = fold(descriptor.merchant_text)
    return next((category for category, pattern in _CATEGORY_WORDS if re.search(pattern, folded)), None)


def has_evidence(descriptor: TransactionDescriptor) -> bool:
    """Whether the customer gave any clue the features can use."""
    return (
        descriptor.amount is not None
        or bool(descriptor.merchant_text)
        or bool(descriptor.date_interpretations)
        or descriptor.channel_hint is not None
    )


def _distance(day: date, window: DateRange) -> int:
    if window.start <= day <= window.end:
        return 0
    return (window.start - day).days if day < window.start else (day - window.end).days


def merchant_similarity(descriptor: TransactionDescriptor, txn: Transaction) -> float:
    """0 to 1: the better of the mean best-token ratio (misspellings) and the token-set ratio (partial names)."""
    if not descriptor.merchant_text:
        return UNKNOWN
    if not txn.merchant_name:
        return 0.0
    wanted, found = words(descriptor.merchant_text), words(txn.merchant_name)
    if not wanted or not found:
        return 0.0
    tokens = [word for word in wanted if len(word) >= 3] or wanted
    per_token = sum(max(fuzz.ratio(word, other) for other in found) for word in tokens) / len(tokens)
    return round(max(per_token, fuzz.token_set_ratio(" ".join(wanted), " ".join(found))) / 100.0, 4)


def _match(hint: object, value: object) -> float:
    if hint is None:
        return UNKNOWN
    return 1.0 if hint == value else 0.0


def _rank(values: Sequence[float]) -> list[float]:
    """Dense rank from 0 for ascending ``values``."""
    ordered = sorted(set(values))
    return [float(ordered.index(value)) for value in values]


def candidate_features(
    descriptor: TransactionDescriptor, candidates: Sequence[Transaction], now: datetime
) -> list[list[float]]:
    """The feature rows of ``candidates``, in their order."""
    days = [txn.occurred_at.astimezone(now.tzinfo).date() for txn in candidates]
    same_day = Counter(days)
    ages = [max(0.0, (now - txn.occurred_at).total_seconds() / 86400.0) for txn in candidates]
    recency_ranks = _rank(ages)
    diffs = [
        abs(txn.amount.amount - descriptor.amount) if descriptor.amount is not None else Decimal(0)
        for txn in candidates
    ]
    closeness = _rank([float(diff) for diff in diffs])
    hint = category_hint(descriptor)
    rows: list[list[float]] = []
    for position, txn in enumerate(candidates):
        if descriptor.amount is not None:
            diff = diffs[position]
            relative = min(MAX_REL_DIFF, float(diff / max(txn.amount.amount, Decimal(1))))
            amount = [1.0, math.log1p(float(diff)), relative]
            currency = _match(descriptor.currency_hint, txn.amount.currency)
            amount_rank = closeness[position]
        else:
            amount, currency, amount_rank = [0.0, UNKNOWN, UNKNOWN], UNKNOWN, UNKNOWN
        if descriptor.date_interpretations:
            distance = min(_distance(days[position], window) for window in descriptor.date_interpretations)
            dated = [1.0, min(MAX_DATE_DISTANCE, float(distance)), 1.0 if descriptor.date_is_ambiguous else 0.0]
        else:
            dated = [0.0, UNKNOWN, 0.0]
        rows.append(
            [
                *amount,
                currency,
                amount_rank,
                *dated,
                1.0 if descriptor.merchant_text else 0.0,
                merchant_similarity(descriptor, txn),
                _match(hint, txn.category) if txn.category is not None or hint is None else 0.0,
                _match(descriptor.channel_hint, txn.channel),
                round(ages[position], 4),
                recency_ranks[position],
                float(same_day[days[position]]),
                float(len(candidates)),
            ]
        )
    return rows


def plausible(row: Sequence[float]) -> bool:
    """The evidence gate over one feature row (see the module docstring)."""
    by_name = dict(zip(FEATURE_NAMES, row, strict=True))
    return (
        (by_name["amount_given"] == 1.0 and by_name["amount_rel_diff"] <= AMOUNT_AGREES)
        or by_name["merchant_similarity"] >= MERCHANT_AGREES
        or (by_name["date_given"] == 1.0 and by_name["date_distance_days"] <= DATE_AGREES)
        or by_name["channel_match"] == 1.0
        or by_name["category_match"] == 1.0
    )
