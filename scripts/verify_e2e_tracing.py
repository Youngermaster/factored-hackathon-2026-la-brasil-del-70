#!/usr/bin/env python3
"""Verify one real demo assistant turn across LiteLLM, PostgreSQL, and Langfuse.

Run from the repository root with the opt-in LiteLLM and Langfuse dependencies.
Credentials are loaded through pydantic-settings and are never printed.
"""

from __future__ import annotations

import asyncio
import os
import sys
import time
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, cast
from uuid import uuid4

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class VerificationError(Exception):
    """A specific required check failed."""


class TraceSettings(BaseSettings):
    """Settings external to bank-agent, with the same .env behavior as its bootstrap."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    openai_api_key: SecretStr | None = None
    trace_test_persona_id: str = "crd-mx-two-cards"
    trace_test_message: str = "¿Cuál es el saldo de mi cuenta de ahorros?"


@dataclass(frozen=True)
class Config:
    model: str
    database_url: Any = field(repr=False)
    public_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    host: str
    persona_id: str
    message: str


def configure() -> Config:
    """Load secrets without displaying them and validate the live demo prerequisites."""
    try:
        from bank_agent.adapters.persistence.postgres.database import database_url
        from bank_agent.bootstrap.settings import load_settings
    except ImportError as error:
        raise VerificationError("bank-agent is missing; use `uv run --package bank-agent`.") from error

    try:
        external = TraceSettings()
    except Exception as error:
        raise VerificationError(f"Cannot load tracing settings ({type(error).__name__}).") from None
    if external.openai_api_key is not None and not os.getenv("LLM_API_KEY_PRIMARY"):
        os.environ["LLM_API_KEY_PRIMARY"] = external.openai_api_key.get_secret_value()
    try:
        settings = load_settings()
    except Exception as error:
        raise VerificationError(f"Cannot load application settings ({type(error).__name__}).") from None
    if not settings.runtime.demo_mode:
        raise VerificationError("Set DEMO_MODE=true so the test persona can complete one-time-code login.")
    if settings.llm.provider != "litellm" or not settings.llm.primary_model:
        raise VerificationError("Set LLM_PROVIDER=litellm and LLM_PRIMARY_MODEL to the configured model.")
    if not settings.workflow.llm_understanding:
        raise VerificationError("Set WORKFLOW_LLM_UNDERSTANDING=true for the inference turn.")
    if not settings.database.is_configured or settings.database.admin_password is None:
        raise VerificationError("Set POSTGRES_APP_PASSWORD and POSTGRES_ADMIN_PASSWORD for the local database.")
    if not settings.langfuse.enabled or settings.langfuse.public_key is None or settings.langfuse.secret_key is None:
        raise VerificationError("Set LANGFUSE_ENABLED=true and both Langfuse keys for the API runtime.")
    return Config(
        model=settings.llm.primary_model,
        database_url=database_url(
            user=settings.database.admin_user,
            password=settings.database.admin_password.get_secret_value(),
            host=settings.database.host,
            port=settings.database.port,
            database=settings.database.db,
        ),
        public_key=settings.langfuse.public_key.get_secret_value(),
        secret_key=settings.langfuse.secret_key.get_secret_value(),
        host=settings.langfuse.base_url.rstrip("/"),
        persona_id=external.trace_test_persona_id,
        message=external.trace_test_message,
    )


def _expect_http(response: Any, status: int, action: str) -> dict[str, Any]:
    if response.status_code != status:
        raise VerificationError(f"{action} failed with HTTP {response.status_code}.")
    try:
        body = response.json()
    except ValueError:
        raise VerificationError(f"{action} returned invalid JSON.") from None
    if not isinstance(body, dict):
        raise VerificationError(f"{action} returned an unexpected response.")
    return body


async def run_assistant_turn(config: Config) -> tuple[str, str, str]:
    """Exercise the real ASGI app, including demo login, the workflow engine, and its LiteLLM adapter."""
    os.environ["LITELLM_LOCAL_MODEL_COST_MAP"] = "True"
    try:
        import httpx
        from bank_agent.asgi import create_app
    except ImportError as error:
        raise VerificationError(
            "The LiteLLM or HTTP dependency is missing; use `uv run --extra litellm --package bank-agent`."
        ) from error
    try:
        app = create_app()
    except Exception as error:
        raise VerificationError(f"Could not start the application ({type(error).__name__}).") from None

    correlation_id = uuid4()
    turn_id = str(correlation_id)
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://trace-check.local") as client:
            csrf = _expect_http(await client.get("/v1/auth/csrf"), 200, "CSRF setup")["csrf_token"]
            headers = {"X-CSRF-Token": csrf}
            start = _expect_http(
                await client.post(
                    "/v1/auth/start",
                    json={"kind": "persona", "persona_id": config.persona_id},
                    headers=headers,
                ),
                200,
                "Demo login start",
            )
            if not start.get("demo_code"):
                raise VerificationError(
                    "The persona has no demo one-time code. Check TRACE_TEST_PERSONA_ID and the seeded database."
                )
            signed_in = _expect_http(
                await client.post(
                    "/v1/auth/verify",
                    json={"challenge_id": start["challenge_id"], "code": start["demo_code"], "language": "es"},
                    headers=headers,
                ),
                200,
                "Demo login verification",
            )
            headers = {"X-CSRF-Token": signed_in["csrf_token"]}
            opened = _expect_http(await client.post("/v1/conversations", headers=headers), 201, "Conversation creation")
            conversation_id = str(opened["conversation_id"])
            turn_response = await client.post(
                f"/v1/conversations/{conversation_id}/turns",
                json={"turn_id": turn_id, "text": config.message},
                headers=headers,
            )
            completed = _expect_http(turn_response, 200, "Assistant inference turn")
            trace_id = turn_response.headers.get("X-Trace-Id", "")
            if len(trace_id) != 32 or not all(char in "0123456789abcdef" for char in trace_id):
                raise VerificationError("The API did not return a valid OpenTelemetry trace ID.")
            if completed.get("replayed") or completed.get("turn_id") != turn_id:
                raise VerificationError("The assistant did not complete the fresh correlation turn.")
    except VerificationError:
        raise
    except Exception as error:
        raise VerificationError(f"Assistant turn failed ({type(error).__name__}).") from None
    finally:
        await app.state.provider.aclose()

    print(f"PASS Assistant turn persisted (conversation {conversation_id}, trace {trace_id}).")
    return trace_id, conversation_id, turn_id


async def read_execution_record(config: Config, trace_id: str, conversation_id: str, turn_id: str) -> dict[str, Any]:
    """Read the durable JSON record directly from the repository's PostgreSQL schema."""
    try:
        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine
    except ImportError as error:
        raise VerificationError("SQLAlchemy is missing from the bank-agent environment.") from error

    engine = create_async_engine(config.database_url, pool_pre_ping=True)
    try:
        async with engine.connect() as connection:
            result = await connection.execute(
                text(
                    "SELECT turn_id, conversation_id, customer_id, document "
                    "FROM app.execution_records WHERE document ->> 'trace_id' = :trace_id"
                ),
                {"trace_id": trace_id},
            )
            rows = result.mappings().all()
    except Exception as error:
        raise VerificationError(
            f"PostgreSQL execution-record query failed ({type(error).__name__}); "
            "check the Docker database and migration."
        ) from None
    finally:
        await engine.dispose()

    if len(rows) != 1:
        raise VerificationError(f"PostgreSQL has {len(rows)} records for correlation {trace_id}; expected exactly one.")
    row = rows[0]
    document = row["document"]
    if not isinstance(document, dict):
        raise VerificationError("PostgreSQL execution record is not a JSON object.")
    if row["turn_id"] != turn_id or row["conversation_id"] != conversation_id:
        raise VerificationError("PostgreSQL turn or conversation ID does not match the assistant turn.")
    if document.get("trace_id") != trace_id or document.get("conversation_id") != conversation_id:
        raise VerificationError("PostgreSQL correlation or conversation ID differs from the assistant turn.")
    if document.get("customer_ref") != row["customer_id"]:
        raise VerificationError("PostgreSQL record customer does not match the row owner.")
    calls = document.get("llm_calls")
    if not isinstance(calls, list) or not calls:
        raise VerificationError("PostgreSQL execution record has no real LiteLLM generation.")
    provider, separator, model_name = config.model.partition("/")
    if not separator or not provider or not model_name:
        raise VerificationError("The configured model has no provider/model name.")
    by_name: dict[str, dict[str, Any]] = {}
    for call in calls:
        if not isinstance(call, dict) or call.get("status") != "ok":
            raise VerificationError("PostgreSQL LLM call is missing or its status is not success (ok).")
        prompt = call.get("prompt")
        if not isinstance(prompt, str) or "@" not in prompt or not all(prompt.rsplit("@", 1)):
            raise VerificationError("PostgreSQL LLM call has no prompt ID/version.")
        if call.get("model_id") != config.model:
            raise VerificationError("PostgreSQL model name differs from LLM_PRIMARY_MODEL.")
        for metric in ("input_tokens", "output_tokens", "latency_ms"):
            if not isinstance(call.get(metric), int) or call[metric] <= 0:
                raise VerificationError(f"PostgreSQL LLM call has no positive {metric}.")
        name = prompt
        if name in by_name:
            raise VerificationError(f"PostgreSQL has duplicate generation name {name}; cannot match calls 1:1.")
        by_name[name] = call
    print(f"PASS PostgreSQL record ({len(by_name)} successful calls, provider {provider}, model {model_name}).")
    return {"calls": by_name, "conversation_id": conversation_id, "turn_id": turn_id}


def _as_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    dump = getattr(value, "model_dump", None)
    if callable(dump):
        result = dump(mode="json")
        for field_name in (
            "trace_id",
            "session_id",
            "user_id",
            "usage_details",
            "cost_details",
            "total_cost",
            "start_time",
            "end_time",
        ):
            result[field_name] = getattr(value, field_name, None)
        return cast(dict[str, Any], result)
    dump_v1 = getattr(value, "dict", None)
    if callable(dump_v1):
        return cast(dict[str, Any], dump_v1())
    return vars(value) if hasattr(value, "__dict__") else {}


def verify_langfuse(config: Config, trace_id: str, record: dict[str, Any]) -> None:
    """Query the generations exported by the API's own OpenTelemetry lifecycle."""
    try:
        from langfuse import Langfuse  # type: ignore[import-not-found]
    except ImportError as error:
        raise VerificationError("Langfuse SDK is missing; add `--with 'langfuse>=4.7,<5'`.") from error

    try:
        client = Langfuse(public_key=config.public_key, secret_key=config.secret_key, host=config.host)
    except Exception as error:
        raise VerificationError(f"Langfuse client setup failed ({type(error).__name__}).") from None
    try:
        deadline = time.monotonic() + 60
        observations: list[dict[str, Any]] = []
        while time.monotonic() < deadline:
            response = client.api.observations.get_many(
                trace_id=trace_id,
                type="GENERATION",
                fields="core,basic,usage,metrics,model,metadata",
                limit=100,
            )
            observations = [_as_dict(item) for item in (getattr(response, "data", response) or [])]
            if len(observations) >= len(record["calls"]) and all(
                (item.get("usage_details") or {}).get("total") is not None
                and (item.get("cost_details") or {}).get("total") is not None
                for item in observations
            ):
                break
            time.sleep(3)
    except Exception as error:
        raise VerificationError(f"Langfuse API query failed ({type(error).__name__}).") from None
    finally:
        try:
            client.shutdown()
        except Exception as error:
            raise VerificationError(f"Langfuse client shutdown failed ({type(error).__name__}).") from None

    generations = [
        item
        for item in observations
        if item.get("traceId", item.get("trace_id")) == trace_id and item.get("type") == "GENERATION"
    ]
    if len(generations) != len(record["calls"]):
        raise VerificationError(
            f"Langfuse returned {len(generations)} generations; PostgreSQL recorded {len(record['calls'])}."
        )
    seen: set[str] = set()
    for generation in generations:
        metadata = generation.get("metadata") or {}
        prompt_id = metadata.get("prompt_id")
        prompt_version = metadata.get("prompt_version")
        name = f"{prompt_id}@{prompt_version}"
        if name not in record["calls"] or name in seen:
            raise VerificationError(f"Langfuse prompt {name!r} has no unique PostgreSQL call.")
        seen.add(name)
        if metadata.get("conversation_id") != record["conversation_id"]:
            raise VerificationError("Langfuse conversation ID differs from PostgreSQL.")
        if metadata.get("correlation_id") != record["turn_id"]:
            raise VerificationError("Langfuse correlation ID differs from PostgreSQL turn ID.")
        if metadata.get("trace_id") != trace_id or not metadata.get("call_id"):
            raise VerificationError("Langfuse has no matching trace and call IDs.")
        if metadata.get("status") != "success":
            raise VerificationError(f"Langfuse {name} has no success status.")
        if not metadata.get("schema_id") or not metadata.get("schema_version"):
            raise VerificationError(f"Langfuse {name} has no schema ID/version.")
        schema_hash = metadata.get("schema_hash")
        if not isinstance(schema_hash, str) or len(schema_hash) != 64 or not schema_hash.startswith(
            str(metadata["schema_version"])
        ):
            raise VerificationError(f"Langfuse {name} has no valid schema hash.")
        if not metadata.get("provider_returned_model_id"):
            raise VerificationError(f"Langfuse {name} has no provider-returned model ID.")
        if generation.get("input") is not None or generation.get("output") is not None:
            raise VerificationError(f"Langfuse {name} exported prompt or response content.")
        if generation.get("user_id") is not None:
            raise VerificationError(f"Langfuse {name} exported a customer identifier.")
        model = generation.get("model")
        provider, _, _ = config.model.partition("/")
        if not isinstance(model, str) or model != config.model:
            raise VerificationError(f"Langfuse {name} provider model differs from LLM_PRIMARY_MODEL.")
        attributes = metadata.get("attributes") or {}
        if attributes.get("gen_ai.provider.name") != provider:
            raise VerificationError(f"Langfuse {name} configured model metadata differs from LLM_PRIMARY_MODEL.")
        usage = generation.get("usage_details") or {}
        remote_input = usage.get("input")
        remote_output = usage.get("output")
        call = record["calls"][name]
        for label, remote, local in (
            ("input", remote_input, call["input_tokens"]),
            ("output", remote_output, call["output_tokens"]),
        ):
            if remote is None:
                raise VerificationError(f"Langfuse {name} has no valid {label} token count.")
            try:
                remote_tokens = int(remote)
            except (TypeError, ValueError):
                raise VerificationError(f"Langfuse {name} has no valid {label} token count.") from None
            if abs(remote_tokens - local) > max(2, round(local * 0.02)):
                raise VerificationError(f"Langfuse {name} {label} tokens differ from PostgreSQL beyond tolerance.")
        latency = metadata.get("latency_ms")
        try:
            remote_latency_ms = Decimal(str(latency))
        except (InvalidOperation, TypeError, ValueError):
            raise VerificationError(f"Langfuse generation {name} has no calculated latency.") from None
        local_latency_ms = Decimal(call["latency_ms"])
        if remote_latency_ms <= 0 or abs(remote_latency_ms - local_latency_ms) > max(
            Decimal(500), local_latency_ms * Decimal("0.25")
        ):
            raise VerificationError(f"Langfuse {name} latency differs from PostgreSQL beyond tolerance.")
        details = generation.get("cost_details") or {}
        cost = details.get("total")
        if cost is None:
            raise VerificationError(f"Langfuse generation {name} has no calculated cost metadata.")
        try:
            remote_cost = Decimal(str(cost))
            local_cost = Decimal(str(call["cost_usd"]))
        except (InvalidOperation, KeyError, TypeError, ValueError):
            raise VerificationError(f"Langfuse {name} has invalid cost metadata.") from None
        if abs(remote_cost - local_cost) > Decimal("0.000001"):
            raise VerificationError(f"Langfuse {name} cost differs from PostgreSQL.")
    print(f"PASS Langfuse: {len(seen)} generations match PostgreSQL calls 1:1.")


async def verify() -> None:
    config = configure()
    trace_id, conversation_id, turn_id = await run_assistant_turn(config)
    record = await read_execution_record(config, trace_id, conversation_id, turn_id)
    verify_langfuse(config, trace_id, record)
    print(f"PASS End-to-end tracing verified for correlation {trace_id}.")


def main() -> int:
    try:
        asyncio.run(verify())
    except VerificationError as error:
        print(f"FAIL {error}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("FAIL Verification interrupted.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
