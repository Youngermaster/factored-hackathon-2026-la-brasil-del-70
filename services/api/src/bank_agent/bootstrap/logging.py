"""Structured JSON logging with redaction.

``configure_logging`` routes both structlog and standard-library loggers (uvicorn, SQLAlchemy) through the
same processor chain, so every record is rendered as one JSON object and passes through
``RedactionProcessor`` before it is written. Redaction runs after exception formatting, so traceback text
is scrubbed too.

Redaction has two parts:

- Key masking: the value of any sensitive key is replaced entirely, at any nesting depth.
- Value scrubbing: every string is searched for emails, LATAM document numbers, phone numbers, and long
  digit runs, which are replaced by a labeled marker such as ``[REDACTED:email]``.
"""

import logging
import re
import sys
from collections.abc import Mapping, MutableMapping
from typing import IO, Any, Final

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

from bank_agent.bootstrap.settings import LogLevel

REDACTED: Final = "[REDACTED]"

# Keys whose whole value is masked, compared after lowercasing and replacing "-" with "_".
SENSITIVE_KEYS: Final[frozenset[str]] = frozenset(
    {
        "address",
        "authorization",
        "cookie",
        "document_number",
        "email",
        "landline_phone",
        "mobile_phone",
        "otp",
        "password",
        "secret",
        "token",
    }
)

# A key is also sensitive when any of its "_"-separated parts is one of these words
# (for example access_token, set_cookie, customer_email, x_authorization).
SENSITIVE_KEY_PARTS: Final[frozenset[str]] = frozenset(
    {
        "address",
        "authorization",
        "cookie",
        "email",
        "otp",
        "passwd",
        "password",
        "phone",
        "secret",
        "token",
    }
)

# A key is also sensitive when it contains one of these fragments anywhere.
SENSITIVE_KEY_FRAGMENTS: Final[tuple[str, ...]] = ("api_key", "apikey", "password", "secret")

# Value patterns, applied in order. Earlier, more specific patterns win over the generic digit rules.
_VALUE_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("email", re.compile(r"[A-Za-z0-9!#$%&'*+/=?^_`{|}~.-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+")),
    # Brazilian CPF, 123.456.789-09, and CNPJ, 12.345.678/0001-95.
    ("document", re.compile(r"(?<!\d)\d{3}\.\d{3}\.\d{3}-\d{2}(?!\d)")),
    ("document", re.compile(r"(?<!\d)\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}(?!\d)")),
    # Mexican CURP, 18 characters: GODE561231HDFRRN09.
    ("document", re.compile(r"(?<![A-Za-z0-9])[A-Z]{4}\d{6}[HMX][A-Z]{5}[A-Z0-9]\d(?![A-Za-z0-9])")),
    # Dot-grouped numbers: Argentine DNI 30.123.456, Colombian CC 1.020.304.050.
    ("document", re.compile(r"(?<![\d.])\d{1,3}(?:\.\d{3}){2,3}(?![\d.])")),
    # Phone numbers with separators: +57 300 123 4567, (11) 91234-5678, 55 1234 5678.
    (
        "phone",
        re.compile(r"(?<![\w+])(?:\+\d{1,3}[ .-]?)?\(?\d{2,4}\)?[ .-]\d{3,5}[ .-]\d{4}(?!\d)"),
    ),
    # Any run of 7 or more digits that is not part of a larger token (UUID groups and hex ids stay intact).
    ("number", re.compile(r"(?<![\w-])\+?\d{7,}(?![\w-])")),
)

_LARGE_INTEGER: Final = 10**6


def is_sensitive_key(key: str) -> bool:
    """Decide whether the value stored under ``key`` must be masked entirely."""
    normalized = key.strip().lower().replace("-", "_")
    if normalized in SENSITIVE_KEYS:
        return True
    if any(part in SENSITIVE_KEY_PARTS for part in normalized.split("_")):
        return True
    return any(fragment in normalized for fragment in SENSITIVE_KEY_FRAGMENTS)


def scrub_text(text: str) -> str:
    """Replace every sensitive-looking substring in ``text`` with a labeled marker."""
    for label, pattern in _VALUE_PATTERNS:
        text = pattern.sub(f"[REDACTED:{label}]", text)
    return text


def redact(value: Any) -> Any:
    """Return a redacted copy of ``value``: mappings, sequences, and sets are walked recursively."""
    if isinstance(value, str):
        return scrub_text(value)
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return "[REDACTED:number]" if abs(value) >= _LARGE_INTEGER else value
    if isinstance(value, Mapping):
        return {key: REDACTED if is_sensitive_key(str(key)) else redact(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set | frozenset):
        return [redact(item) for item in value]
    return value


class RedactionProcessor:
    """structlog processor that masks sensitive keys and scrubs sensitive values in an event dict."""

    def __call__(self, logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
        redacted: MutableMapping[str, Any] = {}
        for key, value in event_dict.items():
            redacted[key] = REDACTED if is_sensitive_key(key) else redact(value)
        return dict(redacted)


def _shared_processors() -> list[Processor]:
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
    ]


def configure_logging(level: LogLevel = "INFO", stream: IO[str] | None = None) -> None:
    """Configure structlog and the standard library to write redacted JSON lines to ``stream``.

    Calling it again replaces the previous configuration, which keeps tests independent.
    """
    shared = _shared_processors()
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.format_exc_info,
            RedactionProcessor(),
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    for existing in list(root.handlers):
        root.removeHandler(existing)
    root.addHandler(handler)
    root.setLevel(level)
    # uvicorn installs its own handlers; route its records through the root handler instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers.clear()
        uvicorn_logger.propagate = True
