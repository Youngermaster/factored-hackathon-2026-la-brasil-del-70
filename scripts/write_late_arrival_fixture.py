"""Write the synthetic update-correctness fixture under data_platform/fixtures/late_arrival/.

Every row is invented by the team (identifiers carry FIX, contact details use example.com) and labeled as a
fixture in FIXTURE.md. The layout mirrors the organizer bucket prefix, so ``LocalSource`` reads it unchanged:

- ``base/``: all 13 tables; transactions for 2024-01-01 and 2024-01-03 (2024-01-02 is missing), an exact
  duplicate row, a primary-key duplicate across partitions, a customer primary-key duplicate, a transcript
  with a missing required value (row quarantine), and a complaints file with an additive column;
- ``late/``: the 2024-01-02 transactions partition, which arrives after a first build and carries a
  primary-key duplicate that must lose to a later partition;
- ``breaking/``: a 2024-01-04 transactions file whose ``amount`` column changed type (every value fails).

Usage: ``uv run python scripts/write_late_arrival_fixture.py`` (writes) or ``--check`` (compares).
"""

import csv
import io
import sys
from pathlib import Path

from bank_data.contracts.tables import table_spec

ROOT = Path(__file__).resolve().parents[1] / "data_platform" / "fixtures" / "late_arrival"
BOM = "﻿"

Row = dict[str, str]


def _csv(table: str, rows: list[Row], extra_columns: tuple[str, ...] = ()) -> str:
    columns = list(table_spec(table).column_names) + list(extra_columns)
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        unknown = set(row) - set(columns)
        if unknown:
            raise ValueError(f"{table}: unknown columns {sorted(unknown)}")
        writer.writerow([row.get(column, "") for column in columns])
    return BOM + buffer.getvalue()


def _daily(table: str, day: str) -> str:
    year, month, date_part = day.split("-")
    return f"{table}/year={year}/month={month}/day={date_part}/{table}_{year}{month}{date_part}.csv"


BRANCHES = [
    {
        "branch_id": "BR-FIX-001",
        "branch_code": "S9001",
        "branch_name": "Fixture Branch Centro",
        "branch_type": "Main",
        "address": "Calle Fixture 1",
        "city": "Ciudad de México",
        "state": "Ciudad de México",
        "country": "México",
        "postal_code": "01000",
        "geographic_zone": "Urbana",
        "phone": "+52 55 0000 0001",
        "email": "branch1@example.com",
        "opening_time": "09:00:00",
        "closing_time": "17:00:00",
        "has_atms": "True",
        "atm_count": "2",
        "has_teller_windows": "True",
        "teller_window_count": "3",
        "latitude": "19.4326077",
        "longitude": "-99.1332080",
        "branch_opening_date": "2001-01-01",
        "branch_status": "Active",
    },
    {
        "branch_id": "BR-FIX-002",
        "branch_code": "S9002",
        "branch_name": "Fixture Branch Norte",
        "branch_type": "Express",
        "address": "Carrera Fixture 2",
        "city": "Bogotá",
        "state": "Cundinamarca",
        "country": "Colombia",
        "postal_code": "110111",
        "geographic_zone": "Urbana",
        "phone": "+57 1 000 0002",
        "email": "branch2@example.com",
        "opening_time": "08:00:00",
        "closing_time": "18:00:00",
        "has_atms": "True",
        "atm_count": "1",
        "has_teller_windows": "True",
        "teller_window_count": "2",
        "latitude": "4.7109886",
        "longitude": "-74.0720920",
        "branch_opening_date": "2005-05-05",
        "branch_status": "Active",
    },
    {
        "branch_id": "BR-FIX-003",
        "branch_code": "S9003",
        "branch_name": "Fixture Branch Sur",
        "branch_type": "Premium",
        "address": "Avenida Fixture 3",
        "city": "Buenos Aires",
        "state": "Ciudad Autónoma de Buenos Aires",
        "country": "Argentina",
        "postal_code": "C1000",
        "geographic_zone": "Urbana",
        "phone": "+54 11 0000 0003",
        "email": "",
        "opening_time": "09:30:00",
        "closing_time": "17:30:00",
        "has_atms": "True",
        "atm_count": "3",
        "has_teller_windows": "True",
        "teller_window_count": "4",
        "latitude": "-34.6036844",
        "longitude": "-58.3815591",
        "branch_opening_date": "2010-10-10",
        "branch_status": "Temporarily Closed",
    },
]


def _customer(customer_id: str, **fields: str) -> Row:
    base = {
        "customer_id": customer_id,
        "document_type": "DNI",
        "gender": "F",
        "city": "Ciudad de México",
        "state": "Ciudad de México",
        "country": "México",
        "detected_accent": "mexican",
        "segment": "Basic",
        "occupation": "Employee",
        "marital_status": "Single",
        "education_level": "University",
        "registration_date": "2020-01-15 10:00:00",
        "registration_branch_id": "BR-FIX-001",
        "customer_status": "Active",
        "last_updated": "2023-12-01 00:00:00",
        "accepts_marketing": "True",
    }
    base.update(fields)
    return base


CUSTOMERS = [
    _customer(
        "CLI-FIX-0001",
        document_number="FIX00001",
        first_name="Ana",
        last_name="Prueba Uno",
        date_of_birth="1990-01-01",
        email="ana.fixture@example.com",
        mobile_phone="+52 55 0000 1001",
        address="Calle Fixture 101",
        postal_code="01000",
        credit_score="700.0",
        estimated_monthly_income="30000.00",
    ),
    _customer(
        "CLI-FIX-0002",
        document_type="CC",
        document_number="1000000002",
        first_name="Luis",
        last_name="Prueba Dos",
        date_of_birth="1985-05-05",
        gender="M",
        email="luis.fixture@example.com",
        mobile_phone="+57 300 000 0002",
        city="Bogotá",
        state="Cundinamarca",
        country="Colombia",
        detected_accent="colombian",
        segment="Premium",
        credit_score="650.0",
        registration_branch_id="BR-FIX-002",
        registration_date="2019-03-01 09:00:00",
        last_updated="2023-12-15 00:00:00",
    ),
    _customer(
        "CLI-FIX-0002",
        document_type="CC",
        document_number="1000000002",
        first_name="Luis",
        last_name="Prueba Dos",
        date_of_birth="1985-05-05",
        gender="M",
        email="luis.fixture@example.com",
        mobile_phone="+57 300 000 0002",
        city="Bogotá",
        state="Cundinamarca",
        country="Colombia",
        detected_accent="colombian",
        segment="Plus",
        credit_score="640.0",
        registration_branch_id="BR-FIX-002",
        registration_date="2019-03-01 09:00:00",
        last_updated="2023-06-01 00:00:00",
    ),
    _customer(
        "CLI-FIX-0003",
        document_number="30000003",
        first_name="Sofía",
        last_name="Prueba Tres",
        date_of_birth="1978-07-07",
        gender="O",
        email="",
        mobile_phone="+54 9 11 0000 0003",
        city="Buenos Aires",
        state="Ciudad Autónoma de Buenos Aires",
        country="Argentina",
        detected_accent="argentine",
        segment="Plus",
        estimated_monthly_income="500000.00",
        registration_branch_id="BR-FIX-999",
        registration_date="2022-11-20 12:00:00",
    ),
    _customer(
        "CLI-FIX-0004",
        document_number="FIX00004",
        first_name="Mario",
        last_name="Prueba Cuatro",
        date_of_birth="2001-02-02",
        gender="M",
        email="mario.fixture@example.com",
        mobile_phone="",
        segment="Student",
        credit_score="580.0",
        estimated_monthly_income="9000.00",
        customer_status="Inactive",
    ),
]


def _product(
    product_id: str, customer_id: str, product_type: str, number: str, currency: str, balance: str, **fields: str
) -> Row:
    base = {
        "product_id": product_id,
        "customer_id": customer_id,
        "product_type": product_type,
        "product_number": number,
        "currency": currency,
        "current_balance": balance,
        "opening_date": "2021-01-01",
        "opening_branch_id": "BR-FIX-001",
        "product_status": "Active",
        "opening_channel": "App",
        "has_linked_app": "True",
        "last_updated": "2024-01-03 12:00:00",
    }
    base.update(fields)
    return base


PRODUCTS = [
    _product(
        "PRD-FIX-CC01",
        "CLI-FIX-0001",
        "Tarjeta Crédito",
        "4000000000000001",
        "USD",
        "1200.50",
        credit_limit="5000.00",
        interest_rate="45.0",
        expiration_date="2027-01-31",
        days_past_due="0.0",
        last_transaction_date="2024-01-02 18:00:00",
    ),
    _product(
        "PRD-FIX-DC01",
        "CLI-FIX-0001",
        "Tarjeta Débito",
        "4000000000000002",
        "USD",
        "350.00",
        interest_rate="0.0",
        expiration_date="2026-12-31",
        product_status="Blocked",
    ),
    _product(
        "PRD-FIX-SV01",
        "CLI-FIX-0001",
        "Cuenta Ahorro",
        "1234500001",
        "USD",
        "8000.00",
        interest_rate="2.5",
        opening_channel="Branch",
        has_linked_app="False",
    ),
    _product(
        "PRD-FIX-CK02",
        "CLI-FIX-0002",
        "Cuenta Corriente",
        "1234500002",
        "COP",
        "2500000.00",
        opening_branch_id="BR-FIX-002",
        interest_rate="0.3",
    ),
    _product(
        "PRD-FIX-PL02",
        "CLI-FIX-0002",
        "Préstamo Personal",
        "LN-0000002",
        "COP",
        "9000000.00",
        credit_limit="10000000.00",
        interest_rate="28.0",
        opening_branch_id="BR-FIX-002",
        days_past_due="30.0",
    ),
    _product(
        "PRD-FIX-MG03",
        "CLI-FIX-0003",
        "Préstamo Hipotecario",
        "MG-0000003",
        "ARS",
        "50000000.00",
        credit_limit="60000000.00",
        interest_rate="45.0",
        opening_branch_id="BR-FIX-003",
        days_past_due="0.0",
    ),
    _product(
        "PRD-FIX-CC03",
        "CLI-FIX-0003",
        "Tarjeta Crédito",
        "5000000000000003",
        "ARS",
        "100000.00",
        credit_limit="400000.00",
        interest_rate="45.0",
        expiration_date="2028-03-31",
        opening_branch_id="BR-FIX-003",
        days_past_due="0.0",
    ),
    _product("PRD-FIX-IN04", "CLI-FIX-0004", "Seguro", "POL-0000004", "USD", "0.0", opening_channel="Web"),
]

AGENTS = [
    {
        "agent_id": "AGT-FIX-01",
        "employee_code": "E90001",
        "first_name": "Carla",
        "last_name": "Agente Uno",
        "email": "carla.agent@example.com",
        "phone": "+52 55 0000 9001",
        "native_accent": "mexican",
        "country_of_origin": "Mexico",
        "assigned_branch_id": "BR-FIX-001",
        "agent_type": "Phone",
        "experience_level": "Senior",
        "languages": "español",
        "specialty": "Fraudes",
        "hire_date": "2018-04-01",
        "avg_csat": "4.5",
        "total_monthly_interactions": "400.0",
        "agent_status": "Active",
        "work_shift": "Morning",
    },
    {
        "agent_id": "AGT-FIX-02",
        "employee_code": "E90002",
        "first_name": "Diego",
        "last_name": "Agente Dos",
        "email": "diego.agent@example.com",
        "phone": "",
        "native_accent": "argentine",
        "country_of_origin": "Argentina",
        "assigned_branch_id": "",
        "agent_type": "Digital",
        "experience_level": "Junior",
        "languages": "español, portugués",
        "specialty": "",
        "hire_date": "2023-02-01",
        "avg_csat": "",
        "total_monthly_interactions": "",
        "agent_status": "Active",
        "work_shift": "Night",
    },
]

CAMPAIGNS = [
    {
        "campaign_id": "CMP-FIX-0001",
        "campaign_name": "CMP_FIX_CC_Jan2024_0001",
        "description": "Campaña de prueba para Tarjeta Crédito",
        "campaign_type": "Email",
        "campaign_objective": "Cross-sell",
        "promoted_product": "Tarjeta Crédito",
        "target_segment": "Basic",
        "target_country": "Mexico",
        "start_date": "2023-12-15",
        "end_date": "2024-02-15",
        "budget": "10000.00",
        "campaign_status": "Completed",
        "expected_conversion_rate": "2.5",
    }
]

RATES = [
    {
        "date": day,
        "source_currency": currency,
        "target_currency": "USD",
        "exchange_rate": rate,
        "buy_rate": rate,
        "sell_rate": rate,
        "source": "Internal",
    }
    for day in ("2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04")
    for currency, rate in (("MXN", "0.058000"), ("COP", "0.000250"), ("ARS", "0.001200"))
]


def _txn(
    transaction_id: str,
    when: str,
    day: str,
    product_id: str,
    customer_id: str,
    kind: str,
    amount: str,
    currency: str,
    **fields: str,
) -> Row:
    base = {
        "transaction_id": transaction_id,
        "transaction_date": when,
        "process_date": day,
        "product_id": product_id,
        "customer_id": customer_id,
        "transaction_type": kind,
        "amount": amount,
        "currency": currency,
        "channel": "App",
        "transaction_country": "México",
        "transaction_city": "Ciudad de México",
        "transaction_status": "Approved",
        "response_code": "00",
        "is_fraud": "False",
        "fraud_score": "3.5",
    }
    if currency == "USD":
        base["amount_usd"] = ""
    base.update(fields)
    return base


TXN_0001 = _txn(
    "TRX-FIX-0001",
    "2024-01-01 15:00:00",
    "2024-01-01",
    "PRD-FIX-CC01",
    "CLI-FIX-0001",
    "Purchase",
    "45.90",
    "USD",
    transaction_category="Food",
    channel="POS",
    merchant_name="Super Fixture",
    merchant_category="Food",
)
TRANSACTIONS_DAY1 = [
    TXN_0001,
    dict(TXN_0001),
    _txn(
        "TRX-FIX-0002", "2024-01-01 16:30:00", "2024-01-01", "PRD-FIX-CC01", "CLI-FIX-0001", "Payment", "200.00", "USD"
    ),
    _txn(
        "TRX-FIX-0003",
        "2024-01-01 18:00:00",
        "2024-01-01",
        "PRD-FIX-CK02",
        "CLI-FIX-0002",
        "Transfer",
        "150000.00",
        "COP",
        channel="Web",
        transaction_country="Colombia",
        transaction_city="Bogotá",
        transaction_status="Pending",
        amount_usd="",
    ),
    _txn(
        "TRX-FIX-0004",
        "2024-01-01 20:00:00",
        "2024-01-01",
        "PRD-FIX-DC01",
        "CLI-FIX-0001",
        "Withdrawal",
        "60.00",
        "USD",
        channel="ATM",
        transaction_status="Declined",
        response_code="51",
    ),
    _txn(
        "TRX-FIX-0005",
        "2024-01-02 03:00:00",
        "2024-01-01",
        "PRD-FIX-SV01",
        "CLI-FIX-0001",
        "Deposit",
        "75.00",
        "USD",
        channel="Web",
    ),
]
TRANSACTIONS_DAY3 = [
    _txn(
        "TRX-FIX-0003",
        "2024-01-01 18:00:00",
        "2024-01-03",
        "PRD-FIX-CK02",
        "CLI-FIX-0002",
        "Transfer",
        "150000.00",
        "COP",
        channel="Web",
        transaction_country="Colombia",
        transaction_city="Bogotá",
        amount_usd="",
    ),
    _txn(
        "TRX-FIX-0010",
        "2024-01-03 11:00:00",
        "2024-01-03",
        "PRD-FIX-CC03",
        "CLI-FIX-0003",
        "Purchase",
        "12000.00",
        "ARS",
        amount_usd="14.40",
        transaction_category="Entertainment",
        channel="POS",
        merchant_name="Cine Fixture",
        merchant_category="Entertainment",
        transaction_country="Argentina",
        transaction_city="Buenos Aires",
    ),
    _txn(
        "TRX-FIX-0011",
        "2024-01-03 12:00:00",
        "2024-01-03",
        "PRD-FIX-SV01",
        "CLI-FIX-0001",
        "Deposit",
        "500.00",
        "USD",
        channel="Branch",
        branch_id="BR-FIX-001",
    ),
    _txn(
        "TRX-FIX-0012",
        "2024-01-03 13:00:00",
        "2024-01-03",
        "PRD-FIX-PL02",
        "CLI-FIX-0002",
        "Payment",
        "300000.00",
        "COP",
        amount_usd="",
        transaction_country="Colombia",
        transaction_city="Bogotá",
        transaction_status="Reversed",
    ),
]
TRANSACTIONS_DAY2_LATE = [
    _txn(
        "TRX-FIX-0010",
        "2024-01-03 11:00:00",
        "2024-01-02",
        "PRD-FIX-CC03",
        "CLI-FIX-0003",
        "Purchase",
        "12000.00",
        "ARS",
        amount_usd="14.40",
        transaction_category="Entertainment",
        channel="POS",
        merchant_name="Cine Fixture",
        merchant_category="Entertainment",
        transaction_country="Argentina",
        transaction_city="Buenos Aires",
        transaction_status="Declined",
        response_code="05",
    ),
    _txn(
        "TRX-FIX-0020",
        "2024-01-02 14:00:00",
        "2024-01-02",
        "PRD-FIX-CC01",
        "CLI-FIX-0001",
        "Purchase",
        "12.00",
        "USD",
        transaction_category="Transport",
        channel="POS",
        merchant_name="Taxi Fixture",
        merchant_category="Transport",
        transaction_country="USA",
        transaction_city="Miami",
    ),
    _txn(
        "TRX-FIX-0021",
        "2024-01-02 15:00:00",
        "2024-01-02",
        "PRD-FIX-MG03",
        "CLI-FIX-0003",
        "Adjustment",
        "1000.00",
        "ARS",
        amount_usd="1.20",
        transaction_country="Argentina",
        transaction_city="Buenos Aires",
    ),
    _txn(
        "TRX-FIX-0022",
        "2024-01-02 16:00:00",
        "2024-01-02",
        "PRD-FIX-CK02",
        "CLI-FIX-0002",
        "Transfer",
        "50000.00",
        "COP",
        amount_usd="",
        channel="Transfer",
        transaction_country="Colombia",
        transaction_city="Bogotá",
        transaction_status="Declined",
        response_code="14",
    ),
]
TRANSACTIONS_DAY4_BREAKING = [
    _txn(
        f"TRX-FIX-004{index}",
        f"2024-01-04 1{index}:00:00",
        "2024-01-04",
        "PRD-FIX-CC01",
        "CLI-FIX-0001",
        "Purchase",
        f"1{index},50 EUR",
        "USD",
    )
    for index in range(3)
]


def _interaction(
    interaction_id: str, when: str, day: str, customer_id: str, agent_id: str, reason: str, **fields: str
) -> Row:
    base = {
        "interaction_id": interaction_id,
        "interaction_date": when,
        "process_date": day,
        "customer_id": customer_id,
        "agent_id": agent_id,
        "interaction_type": "Inbound Call",
        "channel": "Phone",
        "contact_reason": reason,
        "reason_category": reason,
        "duration_seconds": "300.0",
        "wait_time_seconds": "30.0",
        "was_resolved": "True",
        "requires_followup": "False",
        "detected_sentiment": "Neutral",
        "sentiment_score": "0.1",
        "customer_detected_accent": "mexican",
        "agent_used_accent": "mexican",
        "was_escalated": "False",
        "mentioned_products": "",
        "has_transcript": "False",
        "has_recording": "True",
    }
    base.update(fields)
    return base


INTERACTIONS_DAY1 = [
    _interaction(
        "INT-FIX-0001",
        "2024-01-01 15:30:00",
        "2024-01-01",
        "CLI-FIX-0001",
        "AGT-FIX-01",
        "Transaccional",
        mentioned_products="PRD-FIX-CC01",
        has_transcript="True",
    ),
    _interaction(
        "INT-FIX-0002",
        "2024-01-01 17:00:00",
        "2024-01-01",
        "CLI-FIX-0002",
        "AGT-FIX-01",
        "Queja",
        interaction_type="Chat",
        channel="Web Chat",
        detected_sentiment="Negativo",
        sentiment_score="-0.6",
        customer_detected_accent="colombian",
        agent_used_accent="colombian",
        was_escalated="True",
        was_resolved="False",
        requires_followup="True",
        has_transcript="True",
        duration_seconds="",
    ),
]
INTERACTIONS_DAY3 = [
    _interaction(
        "INT-FIX-0003",
        "2024-01-03 10:00:00",
        "2024-01-03",
        "CLI-FIX-0003",
        "AGT-FIX-02",
        "Producto",
        detected_sentiment="Positivo",
        sentiment_score="0.7",
        customer_detected_accent="argentine",
        agent_used_accent="argentine",
    ),
]


def _transcript(transcript_id: str, interaction_id: str, day: str, customer_id: str, **fields: str) -> Row:
    base = {
        "transcript_id": transcript_id,
        "interaction_id": interaction_id,
        "process_date": day,
        "customer_id": customer_id,
        "agent_id": "AGT-FIX-01",
        "full_text": "Cliente: Hola, tengo una consulta.\n\nAgente: Con gusto le ayudo.",
        "customer_text": "Hola, tengo una consulta.",
        "agent_text": "Con gusto le ayudo.",
        "detected_language": "es",
        "detected_accent": "mexican",
        "accent_confidence": "0.9",
        "detected_keywords": "cuenta, banco",
        "mentioned_entities": '{"account_numbers": 0}',
        "detected_intents": "consulta_general",
        "main_topics": "Transaccional",
        "transcription_model": "Whisper v3",
        "audio_quality": "High",
        "duration_seconds": "300.0",
    }
    base.update(fields)
    return base


TRANSCRIPTS_DAY1 = [
    _transcript("TRS-FIX-0001", "INT-FIX-0001", "2024-01-01", "CLI-FIX-0001"),
    _transcript(
        "TRS-FIX-0002",
        "INT-FIX-0002",
        "2024-01-01",
        "CLI-FIX-0002",
        main_topics="Queja",
        detected_accent="colombian",
        duration_seconds="",
    ),
]

SURVEYS_DAY1 = [
    {
        "survey_id": "SRV-FIX-0001",
        "survey_date": "2024-01-01 19:00:00",
        "process_date": "2024-01-01",
        "interaction_id": "INT-FIX-0001",
        "customer_id": "CLI-FIX-0001",
        "agent_id": "AGT-FIX-01",
        "survey_type": "CSAT",
        "send_channel": "SMS",
        "main_score": "4",
        "question_1_text": "¿Cómo calificaría la atención brindada?",
        "question_1_response": "4.0",
        "open_comments": "Buena atención.",
        "comment_sentiment": "Positive",
        "response_time_hours": "3.5",
        "campaign_response_rate": "25.0",
    }
]
SURVEYS_DAY3 = [
    {
        "survey_id": "SRV-FIX-0002",
        "survey_date": "2024-01-04 02:00:00",
        "process_date": "2024-01-03",
        "interaction_id": "INT-FIX-0003",
        "customer_id": "CLI-FIX-0003",
        "agent_id": "AGT-FIX-02",
        "survey_type": "NPS",
        "send_channel": "Email",
        "main_score": "9",
        "nps_category": "Promoter",
        "response_time_hours": "16.0",
    }
]


def _event(event_id: str, when: str, day: str, customer_id: str, event_type: str, **fields: str) -> Row:
    base = {
        "event_id": event_id,
        "event_date": when,
        "process_date": day,
        "customer_id": customer_id,
        "session_id": "SES-FIX-0001",
        "event_type": event_type,
        "event_category": "Navigation",
        "channel": "Android App",
        "platform": "Android",
        "app_version": "5.0.1",
        "page_url": "/home",
        "page_title": "Inicio",
        "action": "view_home",
        "element_id": "home_page",
        "ip_address": "192.0.2.10",
        "ip_country": "México",
        "ip_city": "Ciudad de México",
        "is_mobile": "True",
    }
    base.update(fields)
    return base


EVENTS_DAY1 = [
    _event(
        "EVT-FIX-0001",
        "2024-01-01 14:00:00",
        "2024-01-01",
        "CLI-FIX-0001",
        "Login",
        event_category="Authentication",
        page_url="/login",
        page_title="Iniciar Sesión",
        action="login",
        element_id="login_form",
    ),
    _event(
        "EVT-FIX-0002",
        "2024-01-01 14:01:00",
        "2024-01-01",
        "CLI-FIX-0001",
        "Error",
        page_url="/payments",
        page_title="Pagar Servicios",
        action="initiate_payment",
        element_id="payment_form",
    ),
    _event(
        "EVT-FIX-0003",
        "2024-01-01 14:05:00",
        "2024-01-01",
        "",
        "PageView",
        session_id="SES-FIX-0002",
        channel="Desktop Web",
        platform="Windows",
        browser="Firefox",
        app_version="",
        is_mobile="False",
    ),
]
EVENTS_DAY3 = [
    _event(
        "EVT-FIX-0004",
        "2024-01-03 09:00:00",
        "2024-01-03",
        "CLI-FIX-0003",
        "Click",
        session_id="SES-FIX-0003",
        event_category="Product",
        page_url="/products/credit-card",
        page_title="Tarjeta de Crédito",
        action="view_product",
        element_id="cc_product",
        product_id="PRD-FIX-CC03",
        ip_country="Argentina",
        ip_city="Buenos Aires",
    ),
]


def _complaint(complaint_id: str, when: str, day: str, customer_id: str, **fields: str) -> Row:
    base = {
        "complaint_id": complaint_id,
        "creation_date": when,
        "process_date": day,
        "customer_id": customer_id,
        "case_type": "Claim",
        "category": "Transactions",
        "subcategory": "Cargo no reconocido",
        "reception_channel": "App",
        "description": "Queja de prueba del fixture",
        "priority": "High",
        "status": "Open",
        "sla_breached": "False",
        "is_repeat_complainer": "False",
    }
    base.update(fields)
    return base


COMPLAINTS_DAY1 = [
    _complaint(
        "CMP-FIX-0001",
        "2024-01-01 21:00:00",
        "2024-01-01",
        "CLI-FIX-0001",
        affected_product_id="PRD-FIX-CC01",
        claimed_amount="45.90",
        currency="USD",
    ),
]
COMPLAINTS_DAY3 = [
    {
        **_complaint(
            "CMP-FIX-0002",
            "2024-01-03 08:00:00",
            "2024-01-03",
            "CLI-FIX-0002",
            case_type="Complaint",
            category="Fees",
            subcategory="Cobro indebido",
            reception_channel="Web",
            priority="Medium",
            status="Resolved",
            assigned_agent_id="AGT-FIX-01",
            assignment_date="2024-01-03 09:00:00",
            first_response_date="2024-01-03 10:00:00",
            resolution_date="2024-01-05 10:00:00",
            resolution_days="2.0",
            resolution="Se revisó el caso.",
            resolution_satisfaction="4.0",
        ),
        "channel_detail": "portal",
    }
]

SENDS_DAY1 = [
    {
        "send_id": "SND-FIX-0001",
        "send_date": "2024-01-01 13:00:00",
        "process_date": "2024-01-01",
        "campaign_id": "CMP-FIX-0001",
        "customer_id": "CLI-FIX-0001",
        "send_channel": "Email",
        "template_used": "template_CMP-FIX-0001_1",
        "subject": "Oferta de prueba",
        "send_status": "Sent",
        "was_delivered": "True",
        "was_opened": "True",
        "open_date": "2024-01-01 15:00:00",
        "was_clicked": "False",
        "had_conversion": "False",
        "open_device": "Mobile",
        "open_country": "México",
        "send_cost": "0.0100",
    }
]


def files() -> dict[str, str]:
    """Relative path under the fixture root to file content."""
    written: dict[str, str] = {
        "base/branches.csv": _csv("branches", BRANCHES),
        "base/customers.csv": _csv("customers", CUSTOMERS),
        "base/products.csv": _csv("products", PRODUCTS),
        "base/service_agents.csv": _csv("service_agents", AGENTS),
        "base/marketing_campaigns.csv": _csv("marketing_campaigns", CAMPAIGNS),
        "base/daily_exchange_rates.csv": _csv("daily_exchange_rates", RATES),
        "base/" + _daily("transactions", "2024-01-01"): _csv("transactions", TRANSACTIONS_DAY1),
        "base/" + _daily("transactions", "2024-01-03"): _csv("transactions", TRANSACTIONS_DAY3),
        "base/" + _daily("call_center_interactions", "2024-01-01"): _csv("call_center_interactions", INTERACTIONS_DAY1),
        "base/" + _daily("call_center_interactions", "2024-01-03"): _csv("call_center_interactions", INTERACTIONS_DAY3),
        "base/" + _daily("call_transcripts", "2024-01-01"): _csv("call_transcripts", TRANSCRIPTS_DAY1),
        "base/" + _daily("satisfaction_surveys", "2024-01-01"): _csv("satisfaction_surveys", SURVEYS_DAY1),
        "base/" + _daily("satisfaction_surveys", "2024-01-03"): _csv("satisfaction_surveys", SURVEYS_DAY3),
        "base/" + _daily("digital_events", "2024-01-01"): _csv("digital_events", EVENTS_DAY1),
        "base/" + _daily("digital_events", "2024-01-03"): _csv("digital_events", EVENTS_DAY3),
        "base/" + _daily("complaints", "2024-01-01"): _csv("complaints", COMPLAINTS_DAY1),
        "base/" + _daily("complaints", "2024-01-03"): _csv("complaints", COMPLAINTS_DAY3, ("channel_detail",)),
        "base/" + _daily("campaign_sends", "2024-01-01"): _csv("campaign_sends", SENDS_DAY1),
        "late/" + _daily("transactions", "2024-01-02"): _csv("transactions", TRANSACTIONS_DAY2_LATE),
        "breaking/" + _daily("transactions", "2024-01-04"): _csv("transactions", TRANSACTIONS_DAY4_BREAKING),
    }
    return written


def main(argv: list[str]) -> int:
    check = "--check" in argv[1:]
    stale = []
    for relative, content in files().items():
        path = ROOT / relative
        if check:
            if not path.exists() or path.read_text(encoding="utf-8") != content:
                stale.append(relative)
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    if check and stale:
        print("late_arrival fixture is out of date: " + ", ".join(stale))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
