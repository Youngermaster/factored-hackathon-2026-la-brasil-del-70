from decimal import Decimal

import pytest
from hypothesis import given
from hypothesis import strategies as st
from pydantic import JsonValue

from bank_agent.adapters.llm.redaction import UNREDACTED_VARIABLE_KEYS, Redactor
from bank_agent.domain.intelligence import PromptValue
from bank_agent.domain.money import Currency, Money

REDACTOR = Redactor()

MASKED = [
    # Emails and phones, es and pt.
    ("Escríbanme a maria.lopez@example.com por favor", "Escríbanme a [EMAIL] por favor"),
    ("Meu e-mail é joao_silva+banco@mail.com.br", "Meu e-mail é [EMAIL]"),
    ("Mi celular es +57 300 123 4567", "Mi celular es [PHONE]"),
    ("llámame al 300 1234567", "llámame al [PHONE]"),
    ("Meu telefone é (11) 91234-5678", "Meu telefone é [PHONE]"),
    ("WhatsApp +55 11 91234 5678", "WhatsApp [PHONE]"),
    ("mi número 55 1234 5678", "mi número [PHONE]"),
    ("ligue +5511912345678", "ligue [PHONE]"),
    # LATAM document formats.
    ("Mi CURP es GODE561231HDFRRN09", "Mi CURP es [DOCUMENT]"),
    ("CPF 123.456.789-09", "CPF [DOCUMENT]"),
    ("meu cpf é 12345678909", "meu cpf é [DOCUMENT]"),
    ("CNPJ da empresa 12.345.678/0001-95", "CNPJ da empresa [DOCUMENT]"),
    ("mi cédula es 1.020.304.050", "mi cédula es [DOCUMENT]"),
    ("C.C. 1020304050", "C.C. [DOCUMENT]"),
    ("cc 79123456", "cc [DOCUMENT]"),
    ("cédula de ciudadanía número 1234567", "cédula de ciudadanía número [DOCUMENT]"),
    ("DNI 30.123.456", "DNI [DOCUMENT]"),
    ("mi dni es 30123456", "mi dni es [DOCUMENT]"),
    ("RG 12.345.678-9", "RG [DOCUMENT]"),
    ("documento 30.123.456 de Buenos Aires", "documento [DOCUMENT] de Buenos Aires"),
    ("es el 30.123.456", "es el [DOCUMENT]"),
    # Card numbers and long digit runs.
    ("la tarjeta 4111 1111 1111 1111 no funciona", "la tarjeta [CARD_NUMBER] no funciona"),
    ("cartão 5500-0000-0000-0004", "cartão [CARD_NUMBER]"),
    ("cuenta 0123456789", "cuenta [NUMBER]"),
    # Names.
    ("Hola, me llamo Mariana López y tengo un problema", "Hola, me llamo [NAME] y tengo un problema"),
    ("Mi nombre es Juan Carlos de la Cruz", "Mi nombre es [NAME]"),
    ("Oi, meu nome é João da Silva", "Oi, meu nome é [NAME]"),
    ("me chamo Ana Paula", "me chamo [NAME]"),
    ("Soy Pedro, cliente desde 2019", "Soy [NAME], cliente desde 2019"),
    ("a conta está em nome de Carla Souza", "a conta está em nome de [NAME]"),
]

KEPT = [
    "Me cobraron $1.500.000 en Falabella",
    "Me cobraron 1.500.000 pesos",
    "cobrança de R$ 1.234,56 no cartão",
    "un cargo de COP 2.000.000 ayer",
    "transferí 15000000 pesos",
    "pagué MXN 1,250.00 el 03/04",
    "la compra del 2026-09-20 por 120.50",
    "la tarjeta que termina en 4821",
    "cartão final 1234, fatura de agosto",
    "quiero un préstamo a 24 meses",
    "el 12 de septiembre a las 10:30",
    "soy cliente hace años",
    "sou cliente do banco",
    "Mi saldo en dólares",
    "referencia TXN-A-0004",
    "id 3f2a9c1e-7b4d-4e2a-9c1e-7b4d4e2a9c1e",
    "Pedí 150 000 pesos",
]


@pytest.mark.parametrize(("text", "expected"), MASKED)
def test_masks_personal_data(text: str, expected: str) -> None:
    assert REDACTOR.redact_text(text) == expected


@pytest.mark.parametrize("text", KEPT)
def test_keeps_amounts_dates_last_four_digits_and_ordinary_words(text: str) -> None:
    assert REDACTOR.redact_text(text) == text


def test_masks_sensitive_terms_case_insensitively_as_whole_words() -> None:
    text = "MARIANA dice que mariana no reconoce el cargo; Marianao es otra ciudad"

    assert (
        REDACTOR.redact_text(text, ["Mariana"])
        == "[NAME] dice que [NAME] no reconoce el cargo; Marianao es otra ciudad"
    )


def test_allowlisted_keys_pass_and_every_other_key_is_scrubbed() -> None:
    variables: dict[str, PromptValue] = {
        "customer_message": "Soy Luisa, mi correo es luisa@example.com",
        "facts": ["Cargo de $1.500.000 en Oxxo", "Contacto 300 1234567"],
        "clause_texts": ["Llame al 300 1234567"],
        "reference_date": "2026-09-26",
        "amount": Decimal("12.5"),
        "total": Money(amount=Decimal("1"), currency=Currency.USD),
        "flag_ok": True,
        "count": 12345678901,
        "nothing": None,
    }

    redacted = REDACTOR.redact_variables(variables)

    assert redacted["customer_message"] == "Soy [NAME], mi correo es [EMAIL]"
    assert redacted["facts"] == ["Cargo de $1.500.000 en Oxxo", "Contacto [PHONE]"]
    assert redacted["clause_texts"] == ["Llame al 300 1234567"]
    for key in ("reference_date", "amount", "total", "flag_ok", "count", "nothing"):
        assert redacted[key] == variables[key]
    assert "clause_texts" in UNREDACTED_VARIABLE_KEYS
    assert "customer_message" not in UNREDACTED_VARIABLE_KEYS


def test_redacts_json_string_leaves() -> None:
    value: JsonValue = {
        "merchant_text": "Pago a juan@example.com",
        "items": ["300 1234567", 3],
        "amount": "12.50",
        "n": None,
    }

    assert REDACTOR.redact_json(value) == {
        "merchant_text": "Pago a [EMAIL]",
        "items": ["[PHONE]", 3],
        "amount": "12.50",
        "n": None,
    }


@given(st.text(max_size=200))
def test_redaction_is_idempotent(text: str) -> None:
    once = REDACTOR.redact_text(text, ["Mariana"])

    assert REDACTOR.redact_text(once, ["Mariana"]) == once


@pytest.mark.parametrize(("text", "_expected"), MASKED)
def test_redaction_is_idempotent_on_the_table(text: str, _expected: str) -> None:
    once = REDACTOR.redact_text(text)

    assert REDACTOR.redact_text(once) == once
