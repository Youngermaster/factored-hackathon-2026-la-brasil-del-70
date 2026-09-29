"""Builds the synthetic evaluation world deterministically from a seed (``build_world``).

Twelve persona roles per country (Mexico, Colombia, Argentina), each mirroring a named criterion of
``data_platform/seed/personas.yaml``; segments rotate so every segment appears in every country. Identifiers
start with ``EV`` so they never collide with seeded demo or organizer identifiers.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, timedelta
from functools import cache
from typing import Final

from bank_agent.domain.customer import Customer, CustomerSegment, CustomerStatus
from bank_agent.domain.locale import Country
from bank_agent.domain.masking import MaskedNumber
from bank_agent.domain.money import Currency, Money
from bank_agent.domain.product import Product, ProductStatus, ProductType
from bank_agent.domain.transaction import TransactionStatus as Status
from bank_agent.domain.transaction import TransactionType as Kind
from bank_evals.world import records
from bank_evals.world.model import NOW, Persona, World

DEFAULT_SEED: Final = "bank-eval-world-v1"
SEGMENTS: Final = (CustomerSegment.BASIC, CustomerSegment.PLUS, CustomerSegment.PREMIUM, CustomerSegment.STUDENT)


@dataclass(frozen=True)
class CountryBook:
    """Per-country currency, names, merchants, and amounts (all synthetic)."""

    country: Country
    currency: Currency
    names: tuple[str, ...]
    merchants: dict[str, str]
    amounts: dict[str, str]


BOOKS: Final = {
    Country.MX: CountryBook(
        Country.MX,
        Currency.MXN,
        (
            "Lucia",
            "Mateo",
            "Valeria",
            "Diego",
            "Renata",
            "Emilio",
            "Ximena",
            "Andres",
            "Paola",
            "Hugo",
            "Carla",
            "Rafael",
        ),
        {
            "recent": "TIENDA AURORA",
            "similar": "CAFE LUNA",
            "pending": "FARMACIA CENTRO",
            "old": "LIBROS DEL SUR",
            "large": "ELECTRONICA NORTE",
            "target": "PAPELERIA SOL",
            "declined": "GASOLINERA SOL",
            "payee": "JUAN PEREZ",
            "bill": "PAGO SERVICIO LUZ",
            "other": "MERCADO REAL",
        },
        {
            "recent": "1250.00",
            "similar": "300.00",
            "pending": "640.00",
            "old": "910.00",
            "large": "15000.00",
            "target": "730.00",
            "declined": "200.00",
            "transfer": "1500.00",
            "bill": "850.00",
            "checking": "52300.50",
            "savings": "18000.00",
            "card_balance": "12500.00",
            "card_limit": "60000.00",
            "income": "60000.00",
        },
    ),
    Country.CO: CountryBook(
        Country.CO,
        Currency.COP,
        (
            "Camila",
            "Santiago",
            "Mariana",
            "Julian",
            "Daniela",
            "Felipe",
            "Laura",
            "Sebastian",
            "Natalia",
            "Andres",
            "Paula",
            "Rafael",
        ),
        {
            "recent": "ALMACEN ANDES",
            "similar": "PANADERIA LA 70",
            "pending": "DROGUERIA CENTRAL",
            "old": "LIBRERIA BOGOTA",
            "large": "TECNOLOGIA CARIBE",
            "target": "PAPELERIA NORTE",
            "declined": "ESTACION TERPEL SUR",
            "payee": "MARIA GOMEZ",
            "bill": "PAGO SERVICIO AGUA",
            "other": "TIENDA LA ESQUINA",
        },
        {
            "recent": "85000.00",
            "similar": "18000.00",
            "pending": "42000.00",
            "old": "56000.00",
            "large": "2500000.00",
            "target": "37000.00",
            "declined": "40000.00",
            "transfer": "300000.00",
            "bill": "120000.00",
            "checking": "3450000.00",
            "savings": "5200000.00",
            "card_balance": "1200000.00",
            "card_limit": "8000000.00",
            "income": "9000000.00",
        },
    ),
    Country.AR: CountryBook(
        Country.AR,
        Currency.ARS,
        (
            "Tomas",
            "Sofia",
            "Martin",
            "Lucia",
            "Joaquin",
            "Florencia",
            "Nicolas",
            "Agustina",
            "Federico",
            "Julieta",
            "Ramiro",
            "Rafael",
        ),
        {
            "recent": "KIOSCO DEL SUR",
            "similar": "CAFE LA RAMBLA",
            "pending": "FARMACIA PLAZA",
            "old": "LIBRERIA ATENEO",
            "large": "ELECTRO PAMPA",
            "target": "BAZAR PALERMO",
            "declined": "ESTACION YPF OESTE",
            "payee": "PABLO DIAZ",
            "bill": "PAGO SERVICIO GAS",
            "other": "SUPER LA ESQUINA",
        },
        {
            "recent": "15000.00",
            "similar": "2300.00",
            "pending": "8200.00",
            "old": "9900.00",
            "large": "750000.00",
            "target": "7300.00",
            "declined": "5000.00",
            "transfer": "60000.00",
            "bill": "21000.00",
            "checking": "480000.00",
            "savings": "250000.00",
            "card_balance": "45000.00",
            "card_limit": "300000.00",
            "income": "1800000.00",
        },
    ),
}

ROLES: Final = (
    "acc",
    "crd",
    "crdx",
    "dsp",
    "dspcase",
    "dsprep",
    "cre",
    "crenoinc",
    "creborder",
    "crepast",
    "creapp",
    "other",
)


def card_number(seed: str, product_id: str, prefix: str) -> str:
    digest = hashlib.sha256(f"{seed}:{product_id}".encode()).hexdigest()
    digits = "".join(str(int(char, 16) % 10) for char in digest[:12])
    return f"{prefix}{digits}"


class Builder:
    def __init__(self, seed: str) -> None:
        self.seed, self.world = seed, World()

    def money(self, book: CountryBook, key: str) -> Money:
        return Money.of(book.amounts[key], book.currency)

    def product(self, persona: Persona, book: CountryBook, ref: str, kind: ProductType, **extra: object) -> Product:
        product_id = f"PRD-{persona.customer.customer_id[4:]}-{len(persona.refs) + 1:02d}"
        prefix = {ProductType.CREDIT_CARD: "4", ProductType.DEBIT_CARD: "5"}.get(kind, "6")
        fields: dict[str, object] = {
            "product_id": product_id,
            "customer_id": persona.customer.customer_id,
            "product_type": kind,
            "status": ProductStatus.ACTIVE,
            "masked_number": MaskedNumber.from_full(card_number(self.seed, product_id, prefix + "000")),
            "currency": book.currency,
            "opened_on": date(2022, 3, 1),
            **extra,
        }
        if kind in {ProductType.CREDIT_CARD, ProductType.DEBIT_CARD}:
            fields.setdefault("expires_on", date(2028, 3, 31))
        item = Product.model_validate(fields)
        self.world.products.append(item)
        persona.refs[ref] = item.product_id
        return item

    def txn(
        self,
        persona: Persona,
        book: CountryBook,
        ref: str,
        product: Product,
        amount: str,
        days_ago: int,
        merchant: str,
        status: Status = Status.APPROVED,
        kind: Kind = Kind.PURCHASE,
    ) -> None:
        transaction_id = f"TRX-{persona.customer.customer_id[4:]}-{len(persona.refs) + 1:03d}"
        item = records.transaction(
            transaction_id,
            persona,
            product,
            Money.of(amount, book.currency),
            NOW - timedelta(days=days_ago),
            merchant,
            status,
            kind,
        )
        self.world.transactions.append(item)
        persona.refs[ref] = item.transaction_id

    def persona(self, book: CountryBook, index: int, role: str, demonstrates: str) -> Persona:
        code = book.country.value
        customer = Customer(
            customer_id=f"CLI-EV{code}{index + 1:04d}",  # type: ignore[arg-type]
            country=book.country,
            segment=SEGMENTS[(index + list(BOOKS).index(book.country)) % len(SEGMENTS)],
            status=CustomerStatus.ACTIVE,
            first_name=book.names[index],
        )
        persona = Persona(f"{role}-{code.lower()}", customer, demonstrates)
        self.world.personas[persona.persona_id] = persona
        return persona


@cache
def build_world(seed: str = DEFAULT_SEED) -> World:
    """The evaluation world for ``seed``; cached, so callers must work on ``copy()``."""
    builder = Builder(seed)
    for book in BOOKS.values():
        records.populate(builder, book)
    return builder.world
