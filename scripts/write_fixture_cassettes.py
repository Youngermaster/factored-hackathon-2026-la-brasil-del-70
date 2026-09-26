#!/usr/bin/env python3
"""Write the hand-authored fixture cassettes in ``evals/cassettes/``.

Usage:
    uv run --frozen python scripts/write_fixture_cassettes.py                 write every fixture cassette
    uv run --frozen python scripts/write_fixture_cassettes.py --check         exit 1 when a file is stale or missing
    uv run --frozen python scripts/write_fixture_cassettes.py --output-dir D  use another directory

The language model provider has not been chosen, so no cassette in this repository was recorded from a model.
The replies below were written by the team to exercise parsing, replay, and the Portuguese quality check. Each
file says ``provenance: hand_authored_fixture`` and uses the model id ``fixture/hand-authored``; none of them is
evidence of model quality. Once a provider and key exist, real cassettes are recorded with
``LLM_PROVIDER=cassette LLM_CASSETTE_MODE=record`` and the evaluation (phase 14) uses those instead.

Cassette keys depend on the exact variables, so edit a case here and rerun the script rather than editing a JSON
file by hand; a unit test fails when the committed files differ from this script's output.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import JsonValue

from bank_agent.adapters.llm.cassette import (
    FIXTURE_MODEL_ID,
    Cassette,
    Provenance,
    cassette_key,
    cassette_path,
    write_cassette,
)
from bank_agent.domain.intelligence import PromptRef, TokenUsage
from bank_agent.domain.locale import Language

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPOSITORY_ROOT / "evals" / "cassettes"
AUTHORED_AT = datetime(2026, 9, 26, tzinfo=UTC)
NOTE = (
    "Hand-authored fixture for tests, not a model reply. Replace with a recorded cassette once the provider and "
    "key are chosen."
)
REFERENCE_DATE = "2026-09-26"


@dataclass(frozen=True)
class Case:
    prompt: str
    workflow: str
    case: str
    language: Language
    variables: dict[str, JsonValue]
    output: dict[str, JsonValue] | str
    output_model: str | None
    labels: dict[str, str] = field(default_factory=dict)


def _message(text: str, dialect: str, *, dated: bool) -> dict[str, JsonValue]:
    variables: dict[str, JsonValue] = {"customer_message": text, "dialect_hint": dialect}
    if dated:
        variables["reference_date"] = REFERENCE_DATE
    return variables


def _transaction(**values: JsonValue) -> dict[str, JsonValue]:
    empty: dict[str, JsonValue] = {
        "amount": None,
        "currency_hint": None,
        "merchant_text": None,
        "date_expression": None,
        "channel_hint": None,
        "card_last4_hint": None,
    }
    return {**empty, **values}


def _payment(**values: JsonValue) -> dict[str, JsonValue]:
    empty: dict[str, JsonValue] = {"amount": None, "currency_hint": None, "date_expression": None, "payee_text": None}
    return {**empty, **values}


def _credit(**values: JsonValue) -> dict[str, JsonValue]:
    empty: dict[str, JsonValue] = {
        "product_of_interest": None,
        "requested_amount": None,
        "currency_hint": None,
        "requested_term_months": None,
        "purpose": None,
        "declared_monthly_income": None,
    }
    return {**empty, **values}


ES, PT = Language.ES, Language.PT


def _dispute_cases() -> list[Case]:
    prompt, model, workflow = "extract_dispute_slots@1", "DisputeSlotExtraction", "dispute"
    rows: list[tuple[str, Language, str, str, dict[str, JsonValue]]] = [
        (
            "normal",
            ES,
            "es-MX",
            "No reconozco un cargo de 1250 pesos en Liverpool del 20 de septiembre con mi tarjeta terminación 4821.",
            {
                "intent_candidates": [{"intent": "dispute_new", "confidence": 0.93}],
                "transaction": _transaction(
                    amount="1250", merchant_text="Liverpool", date_expression="20 de septiembre", card_last4_hint="4821"
                ),
                "reason_candidates": ["unrecognized"],
            },
        ),
        (
            "ambiguous",
            ES,
            "es-MX",
            "Hay un cobro raro en mi cuenta, no sé bien de qué es.",
            {
                "intent_candidates": [
                    {"intent": "dispute_new", "confidence": 0.55},
                    {"intent": "payment_status", "confidence": 0.2},
                ],
                "transaction": None,
                "reason_candidates": ["unrecognized", "other"],
            },
        ),
        (
            "out_of_scope",
            ES,
            "es-MX",
            "¿Me recomiendan invertir en criptomonedas este año?",
            {
                "intent_candidates": [{"intent": "unsupported", "confidence": 0.7}],
                "transaction": None,
                "reason_candidates": [],
            },
        ),
        (
            "normal",
            PT,
            "pt-BR",
            "Não reconheço uma cobrança de 1500 pesos no Mercado Livre ontem, no cartão final 7314.",
            {
                "intent_candidates": [{"intent": "dispute_new", "confidence": 0.91}],
                "transaction": _transaction(
                    amount="1500", merchant_text="Mercado Livre", date_expression="ontem", card_last4_hint="7314"
                ),
                "reason_candidates": ["unrecognized"],
            },
        ),
        (
            "ambiguous",
            PT,
            "pt-BR",
            "Tem uma cobrança estranha na minha conta, acho que foi semana passada.",
            {
                "intent_candidates": [
                    {"intent": "dispute_new", "confidence": 0.5},
                    {"intent": "payment_status", "confidence": 0.25},
                ],
                "transaction": _transaction(date_expression="semana passada"),
                "reason_candidates": [],
            },
        ),
        (
            "out_of_scope",
            PT,
            "pt-BR",
            "Vocês podem me indicar um bom seguro de viagem?",
            {
                "intent_candidates": [{"intent": "unsupported", "confidence": 0.72}],
                "transaction": None,
                "reason_candidates": [],
            },
        ),
    ]
    return [
        Case(prompt, workflow, case, language, _message(text, dialect, dated=True), output, model)
        for case, language, dialect, text, output in rows
    ]


def _account_cases() -> list[Case]:
    prompt, model, workflow = "extract_account_inquiry_slots@1", "AccountInquirySlotExtraction", "account_inquiry"
    empty: dict[str, JsonValue] = {"product_hint": None, "statement_period_expression": None, "payment": None}
    rows: list[tuple[str, Language, str, str, dict[str, JsonValue]]] = [
        (
            "normal",
            ES,
            "es-CO",
            "¿Cuál es el saldo de mi cuenta de ahorros terminada en 3390?",
            {**empty, "product_hint": {"product_type": "savings_account", "last4": "3390"}},
        ),
        ("ambiguous", ES, "es-CO", "Quiero saber cómo va lo de mi pago.", {**empty, "payment": _payment()}),
        ("out_of_scope", ES, "es-CO", "¿A qué hora juega la selección el domingo?", empty),
        (
            "normal",
            PT,
            "pt-BR",
            "Quero o resumo do extrato do cartão de crédito final 5521 do mês passado.",
            {
                **empty,
                "product_hint": {"product_type": "credit_card", "last4": "5521"},
                "statement_period_expression": "mês passado",
            },
        ),
        ("ambiguous", PT, "pt-BR", "Fiz um pagamento e não sei se caiu.", {**empty, "payment": _payment()}),
        ("out_of_scope", PT, "pt-BR", "Qual a previsão do tempo para amanhã?", empty),
    ]
    return [
        Case(prompt, workflow, case, language, _message(text, dialect, dated=True), output, model)
        for case, language, dialect, text, output in rows
    ]


def _card_cases() -> list[Case]:
    prompt, model, workflow = "extract_card_support_slots@1", "CardSupportSlotExtraction", "card_support"
    empty: dict[str, JsonValue] = {"card_hint": None, "requested_action": None, "block_reason_candidates": []}
    rows: list[tuple[str, Language, str, str, dict[str, JsonValue]]] = [
        (
            "normal",
            ES,
            "es-AR",
            "Perdí mi tarjeta de débito terminada en 1187, por favor bloquéenla.",
            {
                "card_hint": {"card_type": "debit_card", "last4": "1187"},
                "requested_action": "block",
                "block_reason_candidates": ["lost"],
            },
        ),
        ("ambiguous", ES, "es-AR", "Tengo un problema con la tarjeta.", empty),
        ("out_of_scope", ES, "es-AR", "Quiero cambiar la contraseña de la app del banco.", empty),
        (
            "normal",
            PT,
            "pt-BR",
            "Roubaram meu cartão de crédito, quero bloquear agora.",
            {
                "card_hint": {"card_type": "credit_card", "last4": None},
                "requested_action": "block",
                "block_reason_candidates": ["stolen"],
            },
        ),
        ("ambiguous", PT, "pt-BR", "Meu cartão está esquisito, não sei se bloqueio ou peço outro.", empty),
        ("out_of_scope", PT, "pt-BR", "Vocês vendem ingressos para shows?", empty),
    ]
    return [
        Case(prompt, workflow, case, language, _message(text, dialect, dated=False), output, model)
        for case, language, dialect, text, output in rows
    ]


def _credit_cases() -> list[Case]:
    prompt, model, workflow = "extract_credit_slots@1", "CreditSlotExtraction", "credit"
    rows: list[tuple[str, Language, str, str, dict[str, JsonValue]]] = [
        (
            "normal",
            ES,
            "es-MX",
            "Quiero un préstamo personal de 50000 pesos a 24 meses para remodelar mi casa. Gano 18000 al mes.",
            _credit(
                product_of_interest="personal_loan",
                requested_amount="50000",
                requested_term_months=24,
                purpose="remodelar mi casa",
                declared_monthly_income="18000",
            ),
        ),
        ("ambiguous", ES, "es-MX", "Me interesa algo de crédito, ¿qué tienen?", _credit()),
        ("out_of_scope", ES, "es-MX", "¿Cuánto está el dólar hoy?", _credit()),
        (
            "normal",
            PT,
            "pt-BR",
            "Gostaria de um cartão de crédito com limite de 10 mil, minha renda mensal é de 6500.",
            _credit(product_of_interest="credit_card", requested_amount="10000", declared_monthly_income="6500"),
        ),
        ("ambiguous", PT, "pt-BR", "Será que eu consigo um empréstimo?", _credit()),
        ("out_of_scope", PT, "pt-BR", "Quero abrir uma conta para minha empresa.", _credit()),
    ]
    return [
        Case(prompt, workflow, case, language, _message(text, dialect, dated=False), output, model)
        for case, language, dialect, text, output in rows
    ]


CREDIT_DISCLAIMER = {
    ES: "[fixture] Resultado indicativo con reglas sintéticas; no es una oferta ni una decisión de crédito.",
    PT: "[fixture] Resultado indicativo com regras sintéticas; não é uma oferta nem uma decisão de crédito.",
}


def _phrase_cases() -> list[Case]:
    prompt = "phrase_response@1"
    rows: list[tuple[str, Language, str, dict[str, JsonValue], str]] = [
        (
            "account_inquiry",
            ES,
            "es-CO",
            {
                "response_kind": "answer",
                "facts": ["Cuenta de ahorros terminada en 3390: saldo disponible 12450.00 COP al 2026-09-25 23:59"],
                "clause_texts": ["[fixture] Los saldos se informan con su fecha y hora de corte."],
            },
            "El saldo disponible de su cuenta de ahorros terminada en 3390 es de 12450.00 COP, con corte al 25 de "
            "septiembre de 2026 a las 23:59. Si necesita algo más, con gusto le ayudo.",
        ),
        (
            "account_inquiry",
            PT,
            "pt-BR",
            {
                "response_kind": "answer",
                "facts": ["Conta poupança final 3390: saldo disponível 12450.00 COP em 2026-09-25 23:59"],
                "clause_texts": ["[fixture] Os saldos são informados com a data e a hora de corte."],
            },
            "O saldo disponível da sua conta poupança final 3390 é de 12450.00 COP, com dados até 25 de setembro de "
            "2026 às 23h59. Se precisar de mais alguma coisa, é só me avisar.",
        ),
        (
            "card_support",
            ES,
            "es-AR",
            {
                "response_kind": "action_result",
                "facts": ["Tarjeta de débito terminada en 1187: bloqueo ejecutado y verificado el 2026-09-26 10:42"],
                "clause_texts": ["[fixture] El bloqueo preventivo se confirma solo después de verificarlo."],
            },
            "Listo: su tarjeta de débito terminada en 1187 quedó bloqueada y verificamos el bloqueo el 26 de "
            "septiembre de 2026 a las 10:42.",
        ),
        (
            "card_support",
            PT,
            "pt-BR",
            {
                "response_kind": "action_result",
                "facts": ["Cartão de débito final 1187: bloqueio executado e verificado em 2026-09-26 10:42"],
                "clause_texts": ["[fixture] O bloqueio preventivo só é confirmado depois de verificado."],
            },
            "Pronto: seu cartão de débito final 1187 foi bloqueado, e confirmamos o bloqueio em 26 de setembro de "
            "2026 às 10h42.",
        ),
        (
            "dispute",
            ES,
            "es-MX",
            {
                "response_kind": "action_result",
                "facts": [
                    "Caso de disputa DSP-000123 abierto el 2026-09-26 por un cargo de 1250.00 MXN en Liverpool",
                    "Plazo de respuesta del caso: 10 días hábiles",
                ],
                "clause_texts": ["[fixture] El plazo de respuesta se informa al abrir el caso."],
            },
            "Abrimos su caso de disputa DSP-000123 por el cargo de 1250.00 MXN en Liverpool. El plazo de respuesta "
            "es de 10 días hábiles.",
        ),
        (
            "dispute",
            PT,
            "pt-BR",
            {
                "response_kind": "action_result",
                "facts": [
                    "Contestação DSP-000123 aberta em 2026-09-26 para uma cobrança de 1250.00 MXN na Liverpool",
                    "Prazo de resposta da contestação: 10 dias úteis",
                ],
                "clause_texts": ["[fixture] O prazo de resposta é informado na abertura da contestação."],
            },
            "Abrimos a sua contestação DSP-000123 referente à cobrança de 1250.00 MXN na Liverpool. O prazo de "
            "resposta é de 10 dias úteis.",
        ),
        (
            "credit",
            ES,
            "es-MX",
            {
                "response_kind": "eligibility_result",
                "facts": [
                    "Producto: préstamo personal del catálogo sintético",
                    "Monto solicitado: 50000.00 MXN a 24 meses",
                ],
                "clause_texts": ["[fixture] Los montos altos requieren revisión de una persona."],
                "eligibility_outcome": "review_required",
                "eligibility_reasons": ["El monto solicitado supera el umbral de revisión automática."],
                "disclaimer": CREDIT_DISCLAIMER[ES],
            },
            "Con la información que nos dio, su solicitud de préstamo personal por 50000.00 MXN a 24 meses necesita "
            "la revisión de una persona de nuestro equipo, porque el monto supera el umbral de revisión automática. "
            + CREDIT_DISCLAIMER[ES],
        ),
        (
            "credit",
            PT,
            "pt-BR",
            {
                "response_kind": "eligibility_result",
                "facts": [
                    "Produto: empréstimo pessoal do catálogo sintético",
                    "Valor solicitado: 50000.00 MXN em 24 meses",
                ],
                "clause_texts": ["[fixture] Valores altos precisam da análise de uma pessoa."],
                "eligibility_outcome": "review_required",
                "eligibility_reasons": ["O valor solicitado passa do limite de análise automática."],
                "disclaimer": CREDIT_DISCLAIMER[PT],
            },
            "Com as informações que você passou, o seu pedido de empréstimo pessoal de 50000.00 MXN em 24 meses "
            "precisa da análise de uma pessoa da nossa equipe, porque o valor passa do limite de análise automática. "
            + CREDIT_DISCLAIMER[PT],
        ),
    ]
    return [
        Case(
            prompt,
            workflow,
            "normal",
            language,
            {"workflow": workflow, "dialect_hint": dialect, **extra},
            output,
            None,
        )
        for workflow, language, dialect, extra, output in rows
    ]


def fixture_cases() -> list[Case]:
    return [*_dispute_cases(), *_account_cases(), *_card_cases(), *_credit_cases(), *_phrase_cases()]


def build(case: Case) -> tuple[str, Cassette]:
    prompt = PromptRef.model_validate(case.prompt)
    canonical = json.dumps(case.variables, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    key = cassette_key(prompt, FIXTURE_MODEL_ID, case.language, canonical)
    cassette = Cassette(
        cassette_id=key,
        provenance=Provenance.HAND_AUTHORED_FIXTURE,
        note=NOTE,
        labels={"workflow": case.workflow, "case": case.case},
        prompt=prompt,
        model_id=FIXTURE_MODEL_ID,
        language=case.language,
        kind="text" if isinstance(case.output, str) else "structured",
        output_model=case.output_model,
        variables=case.variables,
        output=case.output,
        usage=TokenUsage(),
        latency_ms=0,
        recorded_at=AUTHORED_AT,
    )
    return key, cassette


def write_all(output_dir: Path) -> list[Path]:
    paths: list[Path] = []
    for case in fixture_cases():
        key, cassette = build(case)
        path = cassette_path(output_dir, cassette.prompt, key)
        write_cassette(path, cassette)
        paths.append(path)
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0] if __doc__ else None)
    parser.add_argument("--check", action="store_true", help="fail when a committed file is stale or missing")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    arguments = parser.parse_args(argv)
    if not arguments.check:
        paths = write_all(arguments.output_dir)
        print(f"wrote {len(paths)} fixture cassettes to {arguments.output_dir}")
        return 0
    stale: list[str] = []
    for case in fixture_cases():
        key, cassette = build(case)
        path = cassette_path(arguments.output_dir, cassette.prompt, key)
        expected = json.dumps(cassette.model_dump(mode="json"), sort_keys=True, indent=2, ensure_ascii=False) + "\n"
        if not path.is_file() or path.read_text(encoding="utf-8") != expected:
            stale.append(str(path.relative_to(arguments.output_dir)))
    for name in stale:
        print(f"stale or missing: {name}", file=sys.stderr)
    return 1 if stale else 0


if __name__ == "__main__":
    sys.exit(main())
