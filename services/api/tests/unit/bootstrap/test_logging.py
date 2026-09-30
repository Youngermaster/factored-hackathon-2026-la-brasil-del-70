import io
import json
import logging

import pytest
import structlog

from bank_agent.bootstrap.logging import REDACTED, configure_logging


@pytest.fixture
def log_stream() -> io.StringIO:
    stream = io.StringIO()
    configure_logging("DEBUG", stream=stream)
    return stream


def _records(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines() if line.strip()]


def test_structlog_events_are_json_lines_with_level_and_utc_timestamp(log_stream: io.StringIO) -> None:
    structlog.get_logger("test").info("turn_completed", latency_ms=12)

    (record,) = _records(log_stream)
    assert record["event"] == "turn_completed"
    assert record["level"] == "info"
    assert record["latency_ms"] == 12
    assert str(record["timestamp"]).endswith("Z")


def test_bound_request_id_is_included(log_stream: io.StringIO) -> None:
    with structlog.contextvars.bound_contextvars(request_id="req-00000042"):
        structlog.get_logger("test").info("handled")

    (record,) = _records(log_stream)
    assert record["request_id"] == "req-00000042"


def test_sensitive_values_never_reach_the_output(log_stream: io.StringIO) -> None:
    structlog.get_logger("test").info(
        "otp_sent to laura@example.com",
        otp="483920",
        customer={"document_number": "1.020.304.050", "segment": "retail"},
        note="CPF 123.456.789-09",
    )

    output = log_stream.getvalue()
    (record,) = _records(log_stream)
    assert record["otp"] == REDACTED
    assert record["customer"] == {"document_number": REDACTED, "segment": "retail"}
    for leaked in ("laura@example.com", "483920", "1.020.304.050", "123.456.789-09"):
        assert leaked not in output


def test_exception_tracebacks_are_scrubbed(log_stream: io.StringIO) -> None:
    try:
        raise ValueError("lookup failed for pedro@example.net with CURP GODE561231HDFRRN09")
    except ValueError:
        structlog.get_logger("test").exception("lookup_failed")

    output = log_stream.getvalue()
    (record,) = _records(log_stream)
    assert "ValueError" in str(record["exception"])
    assert "pedro@example.net" not in output
    assert "GODE561231HDFRRN09" not in output


def test_standard_library_loggers_share_the_redacting_json_output(log_stream: io.StringIO) -> None:
    logging.getLogger("uvicorn.access").warning("GET /customers?email=%s", "rosa@example.com")

    (record,) = _records(log_stream)
    assert record["logger"] == "uvicorn.access"
    assert record["level"] == "warning"
    assert "rosa@example.com" not in log_stream.getvalue()


def test_level_filter_drops_records_below_the_configured_level() -> None:
    stream = io.StringIO()
    configure_logging("WARNING", stream=stream)

    structlog.get_logger("test").info("ignored")
    structlog.get_logger("test").warning("kept")

    assert [record["event"] for record in _records(stream)] == ["kept"]


def test_an_access_log_uvicorn_turned_off_stays_off() -> None:
    access = logging.getLogger("uvicorn.access")
    access.handlers.clear()
    access.propagate = False  # what uvicorn --no-access-log leaves behind
    stream = io.StringIO()
    try:
        configure_logging("INFO", stream=stream)
        access.info('198.51.100.4:50000 - "GET /health/live HTTP/1.1" 200')
        logging.getLogger("uvicorn.error").info("still logged")
    finally:
        access.propagate = True
    assert "198.51.100.4" not in stream.getvalue()
    assert "still logged" in stream.getvalue()
