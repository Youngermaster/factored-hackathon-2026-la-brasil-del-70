"""The ingestion contract of every organizer table, transcribed from ``docs/organizer/DATA_DICTIONARY.md``.

Where profiling the delivered data showed values the dictionary does not list (Spanish product types,
``Pasaporte``, ``México``, Spanish sentiment and contact reasons, the ``Web`` interaction channel), the
accepted values include both vocabularies; silver maps them to one canonical code (``canonical``), using the
``canonical_values`` seed for translations and a lower snake case form otherwise.

This module is the single source of truth: the Pandera schemas, the dbt source and silver contract YAML
(``bank-data codegen``), the committed-sample pseudonymization, and the quality report all read it.
"""

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Literal

CONTRACT_VERSION = "1.0.0"
"""Bumped on any change to a table spec below; recorded per ingest run in the manifest."""

DType = Literal["string", "integer", "decimal", "date", "timestamp", "boolean", "time"]
Layout = Literal["snapshot", "daily"]
PiiKind = Literal[
    "document_number",
    "first_name",
    "last_name",
    "date_of_birth",
    "email",
    "phone",
    "address",
    "product_number",
    "ip_address",
]


@dataclass(frozen=True)
class ColumnSpec:
    name: str
    dtype: DType
    nullable: bool = True
    max_length: int | None = None
    accepted: tuple[str, ...] | None = None
    minimum: Decimal | None = None
    maximum: Decimal | None = None
    precision: tuple[int, int] | None = None
    """``DECIMAL(p, s)`` in silver."""
    pii: PiiKind | None = None
    canonical: str | None = None
    """Silver canonicalization domain: ``snake`` or a domain of the ``canonical_values`` seed."""
    unique: bool = False
    """A dictionary ``UQ`` constraint: reported, not enforced at ingestion (the delivered data violates some)."""
    references: tuple[str, str] | None = None
    """``(table, column)`` of a foreign key; orphans are flagged in silver, never dropped."""

    @property
    def silver_type(self) -> str:
        if self.dtype == "decimal":
            precision, scale = self.precision or (18, 6)
            return f"decimal({precision},{scale})"
        return {
            "string": "varchar",
            "integer": "bigint",
            "date": "date",
            "timestamp": "timestamp",
            "boolean": "boolean",
            "time": "time",
        }[self.dtype]


@dataclass(frozen=True)
class TableSpec:
    name: str
    layout: Layout
    primary_key: tuple[str, ...]
    columns: tuple[ColumnSpec, ...]
    dictionary_rows: int
    order_column: str
    """Primary-key duplicates keep the latest value of this column (``last_updated`` or ``process_date``)."""
    customer_column: str | None = "customer_id"
    """Sampling follows this column; ``None`` for tables that are not customer-scoped."""
    silver_exclude: tuple[str, ...] = field(default=())
    """Columns silver never reads (``digital_events`` reads only what the marts need)."""

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(column.name for column in self.columns)

    def column(self, name: str) -> ColumnSpec:
        for column in self.columns:
            if column.name == name:
                return column
        raise KeyError(name)

    @property
    def silver_columns(self) -> tuple[ColumnSpec, ...]:
        return tuple(column for column in self.columns if column.name not in self.silver_exclude)

    @property
    def foreign_keys(self) -> tuple[ColumnSpec, ...]:
        return tuple(column for column in self.silver_columns if column.references is not None)


def _d(value: str) -> Decimal:
    return Decimal(value)


def text(
    name: str,
    max_length: int | None = None,
    *,
    required: bool = False,
    accepted: tuple[str, ...] | None = None,
    pii: PiiKind | None = None,
    canonical: str | None = None,
    unique: bool = False,
    references: tuple[str, str] | None = None,
) -> ColumnSpec:
    if accepted is not None and canonical is None:
        canonical = "snake"
    return ColumnSpec(
        name,
        "string",
        nullable=not required,
        max_length=max_length,
        accepted=accepted,
        pii=pii,
        canonical=canonical,
        unique=unique,
        references=references,
    )


def integer(name: str, minimum: str | None = None, maximum: str | None = None, *, required: bool = False) -> ColumnSpec:
    return ColumnSpec(
        name,
        "integer",
        nullable=not required,
        minimum=None if minimum is None else _d(minimum),
        maximum=None if maximum is None else _d(maximum),
    )


def decimal(
    name: str,
    precision: tuple[int, int],
    minimum: str | None = None,
    maximum: str | None = None,
    *,
    required: bool = False,
) -> ColumnSpec:
    return ColumnSpec(
        name,
        "decimal",
        nullable=not required,
        precision=precision,
        minimum=None if minimum is None else _d(minimum),
        maximum=None if maximum is None else _d(maximum),
    )


def day(name: str, *, required: bool = False, pii: PiiKind | None = None) -> ColumnSpec:
    return ColumnSpec(name, "date", nullable=not required, pii=pii)


def instant(name: str, *, required: bool = False) -> ColumnSpec:
    return ColumnSpec(name, "timestamp", nullable=not required)


def flag(name: str, *, required: bool = False) -> ColumnSpec:
    return ColumnSpec(name, "boolean", nullable=not required)


def clock(name: str, *, required: bool = False) -> ColumnSpec:
    return ColumnSpec(name, "time", nullable=not required)


CURRENCIES = ("MXN", "COP", "ARS", "USD")
COUNTRIES = ("Mexico", "México", "Colombia", "Argentina")
ACCENTS = ("mexican", "colombian", "argentine", "neutral")
PRODUCT_TYPES = (
    "Checking Account",
    "Savings Account",
    "Credit Card",
    "Debit Card",
    "Personal Loan",
    "Mortgage",
    "Investment",
    "Insurance",
    "Cuenta Corriente",
    "Cuenta Ahorro",
    "Tarjeta Crédito",
    "Tarjeta Débito",
    "Préstamo Personal",
    "Préstamo Hipotecario",
    "Inversión",
    "Seguro",
)
SENTIMENTS = (
    "Very Positive",
    "Positive",
    "Neutral",
    "Negative",
    "Very Negative",
    "Muy Positivo",
    "Positivo",
    "Negativo",
    "Muy Negativo",
)
REASON_CATEGORIES = (
    "Transactional",
    "Product",
    "Technical",
    "Commercial",
    "Complaint",
    "Retention",
    "Transaccional",
    "Producto",
    "Técnico",
    "Comercial",
    "Queja",
    "Retención",
)
MONEY = (15, 2)

CUSTOMERS = TableSpec(
    name="customers",
    layout="snapshot",
    primary_key=("customer_id",),
    dictionary_rows=150_000,
    order_column="last_updated",
    columns=(
        text("customer_id", 20, required=True),
        text("document_number", 20, required=True, pii="document_number", unique=True),
        text(
            "document_type",
            10,
            required=True,
            accepted=("DNI", "CURP", "CC", "CE", "Passport", "Pasaporte"),
            canonical="document_type",
        ),
        text("first_name", 100, required=True, pii="first_name"),
        text("last_name", 100, required=True, pii="last_name"),
        day("date_of_birth", required=True, pii="date_of_birth"),
        text("gender", 1, accepted=("M", "F", "O")),
        text("email", 100, pii="email"),
        text("mobile_phone", 20, pii="phone"),
        text("landline_phone", 20, pii="phone"),
        text("address", 200, pii="address"),
        text("city", 100, required=True),
        text("state", 100, required=True),
        text("country", 50, required=True, accepted=COUNTRIES, canonical="country"),
        text("postal_code", 10),
        text("detected_accent", 50, accepted=ACCENTS),
        text("segment", 50, required=True, accepted=("Premium", "Plus", "Basic", "Student")),
        integer("credit_score", "300", "850"),
        decimal("estimated_monthly_income", (12, 2), "0"),
        text("occupation", 100),
        text("marital_status", 20),
        text("education_level", 50),
        instant("registration_date", required=True),
        text("registration_branch_id", 20, required=True, references=("branches", "branch_id")),
        text("customer_status", 20, required=True, accepted=("Active", "Inactive", "Suspended", "Closed")),
        instant("last_updated", required=True),
        flag("accepts_marketing", required=True),
    ),
)

PRODUCTS = TableSpec(
    name="products",
    layout="snapshot",
    primary_key=("product_id",),
    dictionary_rows=400_000,
    order_column="last_updated",
    columns=(
        text("product_id", 20, required=True),
        text("customer_id", 20, required=True, references=("customers", "customer_id")),
        text("product_type", 50, required=True, accepted=PRODUCT_TYPES, canonical="product_type"),
        text("product_number", 30, required=True, pii="product_number", unique=True),
        text("currency", 3, required=True, accepted=CURRENCIES, canonical="identity"),
        decimal("current_balance", MONEY, required=True),
        decimal("credit_limit", MONEY, "0"),
        decimal("interest_rate", (5, 2), "0", "999.99"),
        day("opening_date", required=True),
        day("expiration_date"),
        text("opening_branch_id", 20, required=True, references=("branches", "branch_id")),
        text("product_status", 20, required=True, accepted=("Active", "Blocked", "Closed", "Suspended")),
        text("opening_channel", 30, required=True, accepted=("Branch", "Web", "App", "Call Center")),
        flag("has_linked_app", required=True),
        integer("days_past_due", "0"),
        instant("last_transaction_date"),
        instant("last_updated", required=True),
    ),
)

BRANCHES = TableSpec(
    name="branches",
    layout="snapshot",
    primary_key=("branch_id",),
    dictionary_rows=350,
    order_column="_process_date",
    customer_column=None,
    columns=(
        text("branch_id", 20, required=True),
        text("branch_code", 10, required=True, unique=True),
        text("branch_name", 100, required=True),
        text("branch_type", 30, required=True, accepted=("Main", "Express", "Premium", "Corporate")),
        text("address", 200, required=True),
        text("city", 100, required=True),
        text("state", 100, required=True),
        text("country", 50, required=True, accepted=COUNTRIES, canonical="country"),
        text("postal_code", 10),
        text(
            "geographic_zone",
            50,
            required=True,
            accepted=("Urban", "Suburban", "Rural", "Urbana", "Suburbana"),
            canonical="geographic_zone",
        ),
        text("phone", 20, required=True),
        text("email", 100),
        clock("opening_time", required=True),
        clock("closing_time", required=True),
        flag("has_atms", required=True),
        integer("atm_count", "0"),
        flag("has_teller_windows", required=True),
        integer("teller_window_count", "0"),
        decimal("latitude", (10, 7), "-90", "90"),
        decimal("longitude", (10, 7), "-180", "180"),
        day("branch_opening_date", required=True),
        text("branch_status", 20, required=True, accepted=("Active", "Temporarily Closed", "Closed")),
    ),
)

SERVICE_AGENTS = TableSpec(
    name="service_agents",
    layout="snapshot",
    primary_key=("agent_id",),
    dictionary_rows=1_200,
    order_column="_process_date",
    customer_column=None,
    columns=(
        text("agent_id", 20, required=True),
        text("employee_code", 15, required=True, unique=True),
        text("first_name", 100, required=True, pii="first_name"),
        text("last_name", 100, required=True, pii="last_name"),
        text("email", 100, required=True, pii="email"),
        text("phone", 20, pii="phone"),
        text("native_accent", 50, required=True, accepted=("mexican", "colombian", "argentine")),
        text("country_of_origin", 50, required=True),
        text("assigned_branch_id", 20, references=("branches", "branch_id")),
        text("agent_type", 30, required=True, accepted=("Phone", "In-Person", "Digital", "Hybrid")),
        text("experience_level", 20, required=True, accepted=("Junior", "Mid-Senior", "Senior", "Specialist")),
        text("languages", 100, required=True),
        text("specialty", 100),
        day("hire_date", required=True),
        decimal("avg_csat", (3, 2), "1", "5"),
        integer("total_monthly_interactions", "0"),
        text("agent_status", 20, required=True, accepted=("Active", "Vacation", "Leave", "Inactive")),
        text("work_shift", 20, required=True, accepted=("Morning", "Afternoon", "Night", "Rotating")),
    ),
)

MARKETING_CAMPAIGNS = TableSpec(
    name="marketing_campaigns",
    layout="snapshot",
    primary_key=("campaign_id",),
    dictionary_rows=200,
    order_column="_process_date",
    customer_column=None,
    columns=(
        text("campaign_id", 20, required=True),
        text("campaign_name", 150, required=True),
        text("description"),
        text("campaign_type", 50, required=True, accepted=("Email", "SMS", "Push", "WhatsApp", "Voice", "Mix")),
        text(
            "campaign_objective",
            100,
            required=True,
            accepted=("Acquisition", "Retention", "Cross-sell", "Up-sell", "Reactivation"),
        ),
        text("promoted_product", 50),
        text("target_segment", 50),
        text("target_country", 50),
        day("start_date", required=True),
        day("end_date", required=True),
        decimal("budget", (12, 2), "0"),
        text("campaign_status", 20, required=True, accepted=("Planned", "Active", "Paused", "Completed")),
        decimal("expected_conversion_rate", (5, 2), "0", "100"),
    ),
)

DAILY_EXCHANGE_RATES = TableSpec(
    name="daily_exchange_rates",
    layout="snapshot",
    primary_key=("date", "source_currency", "target_currency"),
    dictionary_rows=3_000,
    order_column="_process_date",
    customer_column=None,
    columns=(
        day("date", required=True),
        text("source_currency", 3, required=True, accepted=CURRENCIES, canonical="identity"),
        text("target_currency", 3, required=True, accepted=CURRENCIES, canonical="identity"),
        decimal("exchange_rate", (18, 6), "0", required=True),
        decimal("buy_rate", (18, 6), "0"),
        decimal("sell_rate", (18, 6), "0"),
        text("source", 50),
    ),
)

TRANSACTIONS = TableSpec(
    name="transactions",
    layout="daily",
    primary_key=("transaction_id",),
    dictionary_rows=5_000_000,
    order_column="process_date",
    columns=(
        text("transaction_id", 30, required=True),
        instant("transaction_date", required=True),
        day("process_date", required=True),
        text("product_id", 20, required=True, references=("products", "product_id")),
        text("customer_id", 20, required=True, references=("customers", "customer_id")),
        text(
            "transaction_type",
            50,
            required=True,
            accepted=("Deposit", "Withdrawal", "Transfer", "Payment", "Purchase", "Adjustment"),
        ),
        text(
            "transaction_category", 50, accepted=("Food", "Transport", "Services", "Entertainment", "Health", "Other")
        ),
        decimal("amount", MONEY, "0", required=True),
        text("currency", 3, required=True, accepted=CURRENCIES, canonical="identity"),
        decimal("amount_usd", MONEY, "0"),
        text("channel", 30, required=True, accepted=("ATM", "Branch", "Web", "App", "POS", "Transfer")),
        text("branch_id", 20, references=("branches", "branch_id")),
        text("merchant_name", 150),
        text("merchant_category", 50),
        text("transaction_country", 50, required=True, canonical="country"),
        text("transaction_city", 100),
        text("transaction_status", 20, required=True, accepted=("Approved", "Declined", "Pending", "Reversed")),
        text("response_code", 10),
        flag("is_fraud", required=True),
        decimal("fraud_score", (5, 2), "0", "100"),
        decimal("latitude", (10, 7), "-90", "90"),
        decimal("longitude", (10, 7), "-180", "180"),
    ),
)

CALL_CENTER_INTERACTIONS = TableSpec(
    name="call_center_interactions",
    layout="daily",
    primary_key=("interaction_id",),
    dictionary_rows=800_000,
    order_column="process_date",
    columns=(
        text("interaction_id", 30, required=True),
        instant("interaction_date", required=True),
        day("process_date", required=True),
        text("customer_id", 20, required=True, references=("customers", "customer_id")),
        text("agent_id", 20, references=("service_agents", "agent_id")),
        text(
            "interaction_type",
            30,
            required=True,
            accepted=("Inbound Call", "Outbound Call", "Chat", "Email", "Video"),
        ),
        text("channel", 30, required=True, accepted=("Phone", "Web Chat", "WhatsApp", "Email", "App", "Web")),
        text("contact_reason", 100, required=True),
        text("reason_category", 50, required=True, accepted=REASON_CATEGORIES, canonical="reason_category"),
        integer("duration_seconds", "0"),
        integer("wait_time_seconds", "0"),
        flag("was_resolved"),
        flag("requires_followup", required=True),
        text("detected_sentiment", 20, accepted=SENTIMENTS, canonical="sentiment"),
        decimal("sentiment_score", (3, 2), "-1", "1"),
        text("customer_detected_accent", 50, accepted=ACCENTS),
        text("agent_used_accent", 50, accepted=ACCENTS),
        flag("was_escalated", required=True),
        text("mentioned_products", 200),
        flag("has_transcript", required=True),
        flag("has_recording", required=True),
    ),
)

CALL_TRANSCRIPTS = TableSpec(
    name="call_transcripts",
    layout="daily",
    primary_key=("transcript_id",),
    dictionary_rows=200_000,
    order_column="process_date",
    columns=(
        text("transcript_id", 30, required=True),
        text("interaction_id", 30, required=True, references=("call_center_interactions", "interaction_id")),
        day("process_date", required=True),
        text("customer_id", 20, required=True, references=("customers", "customer_id")),
        text("agent_id", 20, required=True, references=("service_agents", "agent_id")),
        text("full_text", required=True),
        text("customer_text"),
        text("agent_text"),
        text("detected_language", 10, required=True),
        text("detected_accent", 50, accepted=ACCENTS),
        decimal("accent_confidence", (3, 2), "0", "1"),
        text("detected_keywords", 500),
        text("mentioned_entities"),
        text("detected_intents", 300),
        text("main_topics", 300),
        text("transcription_model", 50, required=True),
        text("audio_quality", 20, accepted=("High", "Medium", "Low")),
        integer("duration_seconds", "0", required=True),
    ),
)

SATISFACTION_SURVEYS = TableSpec(
    name="satisfaction_surveys",
    layout="daily",
    primary_key=("survey_id",),
    dictionary_rows=250_000,
    order_column="process_date",
    columns=(
        text("survey_id", 30, required=True),
        instant("survey_date", required=True),
        day("process_date", required=True),
        text("interaction_id", 30, references=("call_center_interactions", "interaction_id")),
        text("customer_id", 20, required=True, references=("customers", "customer_id")),
        text("agent_id", 20, references=("service_agents", "agent_id")),
        text("survey_type", 20, required=True, accepted=("CSAT", "NPS", "CES"), canonical="identity"),
        text("send_channel", 30, required=True, accepted=("Email", "SMS", "IVR", "App", "Web")),
        integer("main_score", "0", "10", required=True),
        text("nps_category", 20, accepted=("Promoter", "Passive", "Detractor")),
        text("question_1_text"),
        integer("question_1_response", "1", "5"),
        text("question_2_text"),
        integer("question_2_response", "1", "5"),
        text("question_3_text"),
        integer("question_3_response", "1", "5"),
        text("open_comments"),
        text("comment_sentiment", 20, accepted=SENTIMENTS, canonical="sentiment"),
        decimal("response_time_hours", (8, 2), "0"),
        decimal("campaign_response_rate", (5, 2), "0", "100"),
    ),
)

SURVEY_SCORE_RANGES: dict[str, tuple[int, int]] = {"CSAT": (1, 5), "NPS": (0, 10), "CES": (1, 7)}
"""``main_score`` range by ``survey_type`` (CES uses the common seven-point scale)."""

DIGITAL_EVENTS = TableSpec(
    name="digital_events",
    layout="daily",
    primary_key=("event_id",),
    dictionary_rows=10_000_000,
    order_column="process_date",
    silver_exclude=(
        "browser",
        "page_title",
        "element_id",
        "event_value",
        "ip_address",
        "ip_city",
        "referrer",
        "utm_source",
        "utm_medium",
        "utm_campaign",
    ),
    columns=(
        text("event_id", 30, required=True),
        instant("event_date", required=True),
        day("process_date", required=True),
        text("customer_id", 20, references=("customers", "customer_id")),
        text("session_id", 50, required=True),
        text(
            "event_type",
            50,
            required=True,
            accepted=("PageView", "Click", "FormSubmit", "Login", "Logout", "Error", "Purchase"),
        ),
        text("event_category", 50, required=True, accepted=("Navigation", "Transaction", "Authentication", "Product")),
        text("channel", 30, required=True, accepted=("Android App", "iOS App", "Desktop Web", "Mobile Web")),
        text("platform", 30, accepted=("Android", "iOS", "Windows", "MacOS", "Linux")),
        text("browser", 50),
        text("app_version", 20),
        text("page_url", 300),
        text("page_title", 200),
        text("action", 100),
        text("element_id", 100),
        text("product_id", 20, references=("products", "product_id")),
        decimal("event_value", MONEY),
        integer("duration_seconds", "0"),
        text("ip_address", 45, pii="ip_address"),
        text("ip_country", 50, canonical="country"),
        text("ip_city", 100),
        flag("is_mobile", required=True),
        text("referrer", 300),
        text("utm_source", 100),
        text("utm_medium", 100),
        text("utm_campaign", 100),
    ),
)

COMPLAINTS = TableSpec(
    name="complaints",
    layout="daily",
    primary_key=("complaint_id",),
    dictionary_rows=80_000,
    order_column="process_date",
    columns=(
        text("complaint_id", 30, required=True),
        instant("creation_date", required=True),
        day("process_date", required=True),
        text("customer_id", 20, required=True, references=("customers", "customer_id")),
        text("case_type", 30, required=True, accepted=("Complaint", "Claim", "Request", "Suggestion")),
        text("category", 100, required=True),
        text("subcategory", 100),
        text(
            "reception_channel",
            30,
            required=True,
            accepted=("Call Center", "Email", "Web", "App", "Branch", "Regulator"),
        ),
        text("affected_product_id", 20, references=("products", "product_id")),
        text("related_branch_id", 20, references=("branches", "branch_id")),
        text("origin_interaction_id", 30, references=("call_center_interactions", "interaction_id")),
        text("description", required=True),
        decimal("claimed_amount", MONEY, "0"),
        text("currency", 3, accepted=CURRENCIES, canonical="identity"),
        text("priority", 20, required=True, accepted=("Low", "Medium", "High", "Critical")),
        text(
            "status",
            30,
            required=True,
            accepted=("Open", "In Process", "Escalated", "Resolved", "Closed", "Rejected"),
        ),
        text("assigned_agent_id", 20, references=("service_agents", "agent_id")),
        instant("assignment_date"),
        instant("first_response_date"),
        instant("resolution_date"),
        instant("closing_date"),
        flag("sla_breached", required=True),
        integer("resolution_days", "0"),
        text("resolution"),
        decimal("compensation_granted", MONEY, "0"),
        integer("resolution_satisfaction", "1", "5"),
        flag("is_repeat_complainer", required=True),
    ),
)

CAMPAIGN_SENDS = TableSpec(
    name="campaign_sends",
    layout="daily",
    primary_key=("send_id",),
    dictionary_rows=2_000_000,
    order_column="process_date",
    columns=(
        text("send_id", 30, required=True),
        instant("send_date", required=True),
        day("process_date", required=True),
        text("campaign_id", 20, required=True, references=("marketing_campaigns", "campaign_id")),
        text("customer_id", 20, required=True, references=("customers", "customer_id")),
        text("send_channel", 30, required=True, accepted=("Email", "SMS", "Push", "WhatsApp", "Voice")),
        text("template_used", 100),
        text("subject", 200),
        text("send_status", 20, required=True, accepted=("Sent", "Failed", "Bounced", "Blocked")),
        flag("was_delivered", required=True),
        flag("was_opened"),
        instant("open_date"),
        flag("was_clicked"),
        instant("click_date"),
        integer("click_count", "0"),
        flag("had_conversion", required=True),
        instant("conversion_date"),
        decimal("conversion_value", MONEY, "0"),
        text("open_device", 30),
        text("open_country", 50, canonical="country"),
        text("failure_reason", 200),
        decimal("send_cost", (10, 4), "0"),
    ),
)

TABLES: tuple[TableSpec, ...] = (
    BRANCHES,
    CUSTOMERS,
    DAILY_EXCHANGE_RATES,
    MARKETING_CAMPAIGNS,
    PRODUCTS,
    SERVICE_AGENTS,
    TRANSACTIONS,
    CALL_CENTER_INTERACTIONS,
    CALL_TRANSCRIPTS,
    SATISFACTION_SURVEYS,
    DIGITAL_EVENTS,
    COMPLAINTS,
    CAMPAIGN_SENDS,
)
TABLES_BY_NAME: dict[str, TableSpec] = {table.name: table for table in TABLES}


def table_spec(name: str) -> TableSpec:
    try:
        return TABLES_BY_NAME[name]
    except KeyError as error:
        raise KeyError(f"unknown table {name!r}") from error
