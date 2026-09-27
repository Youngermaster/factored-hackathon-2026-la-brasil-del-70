"""The resolver dataset: queries with labels by construction from gold transactions.

For each use, target transactions are sampled by a salted hash. A query's reference instant is the target's time
plus a hashed offset of 0 to 20 days. Customers are split 70/15/15 by a salted hash; train and dev reference instants
fall before the cutoff and test instants after the cutoff plus the gap, from test customers only
(``customer_temporal_split``). Candidates are the customer's own transactions inside the use's window before the
reference instant: the country's dispute window (``DSP-*-1``) for ``dispute``, payments and transfers inside
``ACC-ALL-2`` for ``payment_lookup``. In dev and test, 10% of queries drop the target from the candidates
(``target_absent``): the right behavior there is to not auto-select anything. Descriptions come from
``describe`` (30% in Portuguese), and descriptors from the engine's deterministic understanding.
"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import yaml

from bank_agent.application.understanding.descriptor import deterministic_descriptor
from bank_agent.domain.intelligence import TransactionDescriptor
from bank_agent.domain.locale import Country
from bank_agent.domain.transaction import Transaction, TransactionType
from bank_ml.common.cards import DatasetCard, label_distribution
from bank_ml.common.hashing import rows_digest, salted_order, salted_unit
from bank_ml.common.reports import REPOSITORY_ROOT
from bank_ml.common.seeds import rng
from bank_ml.common.splits import Split, TemporalConfig, customer_temporal_split
from bank_ml.resolver.describe import describe
from bank_ml.resolver.gold import GoldReader

SALT = "resolver-split-v1"
VERSION = "resolver-v1"
USE_TYPES = {
    "dispute": (TransactionType.PURCHASE, TransactionType.WITHDRAWAL, TransactionType.ADJUSTMENT),
    "payment_lookup": (TransactionType.PAYMENT, TransactionType.TRANSFER),
}
CLAUSES = REPOSITORY_ROOT / "policies" / "clauses"


def _param(path: Path, name: str) -> int:
    front = path.read_text(encoding="utf-8").split("---")[1]
    return int(yaml.safe_load(front)["params"][name])


def windows() -> dict[str, dict[Country, int]]:
    """Window days per use and country, read from the policy clauses (single source of truth)."""
    statement = _param(CLAUSES / "acc" / "ACC-ALL-2.en.md", "max_statement_days")
    return {
        "dispute": {c: _param(CLAUSES / "dsp" / f"DSP-{c.value}-1.en.md", "dispute_window_days") for c in Country},
        "payment_lookup": dict.fromkeys(Country, statement),
    }


@dataclass(frozen=True)
class ResolverConfig:
    temporal: TemporalConfig = field(default_factory=lambda: TemporalConfig(cutoff=date(2026, 1, 1), gap_days=30))
    sizes: dict[str, int] = field(default_factory=lambda: {"train": 3000, "dev": 1000, "test": 1000})
    sample_share: float = 0.05
    absent_share: float = 0.10
    portuguese_share: float = 0.30
    max_offset_days: int = 20


@dataclass(frozen=True)
class Query:
    query_id: str
    use: str
    split: Split
    language: str
    country: Country
    customer_id: str
    now: datetime
    text: str
    clues: dict[str, str]
    descriptor: TransactionDescriptor
    candidates: list[Transaction]
    target_id: str | None
    """``None`` when the target was removed from the candidates (``target_absent``)."""


@dataclass(frozen=True)
class ResolverDataset:
    queries: list[Query]
    card: DatasetCard

    def split(self, name: str, use: str | None = None) -> list[Query]:
        return [q for q in self.queries if q.split == name and (use is None or q.use == use)]


def _now(target_id: str, occurred_at: datetime, config: ResolverConfig, latest: datetime) -> datetime:
    days = int(salted_unit(SALT + ":offset", target_id) * (config.max_offset_days + 1))
    hours = int(salted_unit(SALT + ":hour", target_id) * 12)
    return min(occurred_at + timedelta(days=days, hours=hours), latest)


def build_dataset(gold_dir: Path, config: ResolverConfig | None = None) -> ResolverDataset:
    config = config or ResolverConfig()
    reader = GoldReader(gold_dir)
    try:
        queries = [query for use in USE_TYPES for query in _queries(reader, use, config)]
    finally:
        reader.close()
    return ResolverDataset(queries, _card(queries, config))


def _select(
    reader: GoldReader, types: tuple[str, ...], config: ResolverConfig
) -> tuple[list[tuple[str, str, datetime, Split]], dict[str, Country]]:
    """Targets per split up to the configured sizes, decided from ids and times only (no transaction loaded)."""
    sampled = sorted(reader.sampled_targets(types, config.sample_share), key=lambda row: salted_order(SALT, row[0]))
    countries = reader.countries(sorted({row[1] for row in sampled}))
    latest = reader.latest()
    counts: Counter[str] = Counter()
    chosen: list[tuple[str, str, datetime, Split]] = []
    for target_id, customer, occurred_at in sampled:
        if customer not in countries:
            continue
        now = _now(target_id, occurred_at, config, latest).astimezone(ZoneInfo(countries[customer].timezone_name))
        split = customer_temporal_split(customer, now, config.temporal, SALT)
        if split is None or counts[split] >= config.sizes[split]:
            continue
        counts[split] += 1
        chosen.append((target_id, customer, now, split))
        if all(counts[name] >= size for name, size in config.sizes.items()):
            break
    return chosen, countries


def _queries(reader: GoldReader, use: str, config: ResolverConfig) -> list[Query]:
    types = tuple(t.value for t in USE_TYPES[use])
    chosen, countries = _select(reader, types, config)
    transactions = reader.transactions_of(sorted({customer for _, customer, _, _ in chosen}))
    window = windows()[use]
    queries: list[Query] = []
    for target_id, customer, now, split in chosen:
        own = transactions[customer]
        target = next(txn for txn in own if txn.transaction_id == target_id)
        country = countries[customer]
        start = now - timedelta(days=window[country])
        candidates = [t for t in own if start <= t.occurred_at <= now and t.transaction_type.value in types]
        absent = split != "train" and salted_unit(SALT + ":absent", target_id) < config.absent_share
        if absent:
            candidates = [t for t in candidates if t.transaction_id != target_id]
            if not candidates:
                continue
        query_id = f"{use}:{target_id}"
        language = "pt" if salted_unit(SALT + ":language", target_id) < config.portuguese_share else "es"
        today = now.date()
        day = target.occurred_at.astimezone(now.tzinfo).date()
        generator = rng("describe", query_id)
        description = describe(
            target, use=use, country=country, language=language, today=today, day=day, generator=generator
        )
        currencies = frozenset(t.amount.currency for t in candidates)
        descriptor = deterministic_descriptor(
            description.text, today, currencies if len(currencies) == 1 else frozenset(), start.date()
        )
        target_or_none = None if absent else target_id
        queries.append(
            Query(
                query_id,
                use,
                split,
                language,
                country,
                customer,
                now,
                description.text,
                description.clues,
                descriptor,
                candidates,
                target_or_none,
            )
        )
    return queries


def _card(queries: list[Query], config: ResolverConfig) -> DatasetCard:
    rows = [
        {"query_id": q.query_id, "split": q.split, "text": q.text, "target": q.target_id,
         "candidates": [t.transaction_id for t in q.candidates], "now": q.now.isoformat()}
        for q in queries
    ]  # fmt: skip
    sizes = Counter(len(q.candidates) for q in queries)
    return DatasetCard(
        name="resolver",
        version=VERSION,
        description=(
            "Resolver queries with labels by construction: gold transactions described by deterministic es and pt "
            "templates (slang amounts, relative dates, misspelled or partial merchants, partial information)."
        ),
        sources=["gold.transactions_serving (read only)", "gold.customers_serving (country only)"],
        filters=[
            f"targets sampled by a salted md5 at share {config.sample_share}",
            f"target-absent queries in dev and test at share {config.absent_share}",
            "windows from DSP-*-1 (dispute) and ACC-ALL-2 (payment lookup)",
        ],
        split_method=(
            f"customers 70/15/15 by salted hash ({SALT}); train and dev before {config.temporal.cutoff}, test after "
            f"the cutoff plus {config.temporal.gap_days} days, from test customers only"
        ),
        rows_per_split=dict(Counter(q.split for q in queries)),
        label_distribution=label_distribution((q.split, f"{q.use}:{q.language}:{q.country.value}") for q in queries),
        content_hash=rows_digest(rows),
        provenance=dict(
            Counter("target_absent" if q.target_id is None else "labeled_by_construction" for q in queries)
        ),
        notes=[f"candidate count distribution: {dict(sorted(sizes.items()))}"],
        parameters={"sizes": config.sizes, "portuguese_share": config.portuguese_share},
    )
