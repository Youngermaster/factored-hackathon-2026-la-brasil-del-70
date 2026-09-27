"""Structured logging for the data platform, with a filter that masks configured secret values.

Messages and ``extra`` fields are written as one JSON object per line on standard error. Any occurrence of
a secret (the S3 access key, secret key, or bucket name) in a message, an argument, or an extra field is
replaced by ``[redacted]`` before the record is emitted, as a second line of defense behind error messages
that never include those values in the first place.
"""

import json
import logging
from collections.abc import Iterable
from typing import Any

REDACTED = "[redacted]"
_STANDARD_ATTRIBUTES = frozenset(vars(logging.makeLogRecord({})).keys()) | {"message", "asctime"}


def _mask(value: str, secrets: tuple[str, ...]) -> str:
    for secret in secrets:
        value = value.replace(secret, REDACTED)
    return value


class SecretMaskingFilter(logging.Filter):
    def __init__(self, secrets: Iterable[str]) -> None:
        super().__init__()
        self._secrets = tuple(sorted({secret for secret in secrets if secret}, key=len, reverse=True))

    def filter(self, record: logging.LogRecord) -> bool:
        if not self._secrets:
            return True
        record.msg = _mask(str(record.msg), self._secrets)
        if record.args:
            record.args = tuple(_mask(str(argument), self._secrets) for argument in record.args)
        for name, value in list(vars(record).items()):
            if name not in _STANDARD_ATTRIBUTES and isinstance(value, str):
                setattr(record, name, _mask(value, self._secrets))
        if record.exc_info and record.exc_info[1] is not None:
            record.exc_text = _mask(logging.Formatter().formatException(record.exc_info), self._secrets)
            record.exc_info = None
        return True


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname.lower(),
            "logger": record.name,
            "event": record.getMessage(),
        }
        for name, value in vars(record).items():
            if name not in _STANDARD_ATTRIBUTES:
                payload[name] = value
        if record.exc_text:
            payload["exception"] = record.exc_text
        elif record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(secrets: Iterable[str], level: int = logging.INFO) -> None:
    """Route ``bank_data`` loggers to standard error as JSON, masking ``secrets``."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    handler.addFilter(SecretMaskingFilter(secrets))
    logger = logging.getLogger("bank_data")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
