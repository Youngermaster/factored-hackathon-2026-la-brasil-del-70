"""Pure ASGI middleware: request ids, trace ids, security headers, and the request body limit."""

import re
from collections.abc import Awaitable, Callable
from typing import Final

import structlog
from starlette.datastructures import MutableHeaders
from starlette.responses import Response
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER: Final = "X-Request-ID"
TRACE_ID_HEADER: Final = "X-Trace-Id"
_VALID_REQUEST_ID: Final = re.compile(r"^[A-Za-z0-9-]{8,64}$")


class RequestIdMiddleware:
    """Assigns every HTTP request an id, binds it to the log context, and echoes it in the response.

    An inbound ``X-Request-ID`` is reused only when it matches ``^[A-Za-z0-9-]{8,64}$``; anything else is
    replaced with a fresh id from ``id_factory``, so clients cannot inject arbitrary text into logs.
    """

    def __init__(self, app: ASGIApp, id_factory: Callable[[], str]) -> None:
        self._app = app
        self._id_factory = id_factory

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        request_id = self._resolve_request_id(scope)
        scope.setdefault("state", {})["request_id"] = request_id

        async def send_with_request_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers[REQUEST_ID_HEADER] = request_id
            await send(message)

        with structlog.contextvars.bound_contextvars(request_id=request_id):
            await self._app(scope, receive, send_with_request_id)

    def _resolve_request_id(self, scope: Scope) -> str:
        header_name = REQUEST_ID_HEADER.lower().encode("latin-1")
        for name, value in scope.get("headers", []):
            if name == header_name:
                candidate: str = value.decode("latin-1")
                if _VALID_REQUEST_ID.fullmatch(candidate):
                    return candidate
                break
        return self._id_factory()


class TraceIdMiddleware:
    """Answers every HTTP request with the id of its trace in ``X-Trace-Id``.

    The id comes from ``current_trace_id`` when the response starts, inside the server span the OpenTelemetry
    instrumentation opened, so it is the trace a support engineer finds in Jaeger and the one the turn's execution
    record stores. Responses outside a trace (health probes, or no tracer) carry no header.
    """

    def __init__(self, app: ASGIApp, current_trace_id: Callable[[], str | None]) -> None:
        self._app = app
        self._current_trace_id = current_trace_id

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        async def send_with_trace_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                trace_id = self._current_trace_id()
                if trace_id is not None:
                    MutableHeaders(scope=message)[TRACE_ID_HEADER] = trace_id
            await send(message)

        await self._app(scope, receive, send_with_trace_id)


API_CSP: Final = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
DOCS_CSP: Final = (
    "default-src 'none'; script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net; "
    "style-src 'self' https://cdn.jsdelivr.net; img-src 'self' data: https://fastapi.tiangolo.com; "
    "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'"
)
PERMISSIONS_POLICY: Final = (
    "accelerometer=(), autoplay=(), camera=(), display-capture=(), geolocation=(), gyroscope=(), "
    "magnetometer=(), microphone=(), payment=(), publickey-credentials-get=(), usb=()"
)
HSTS: Final = "max-age=63072000; includeSubDomains"
_BASE_HEADERS: Final = (
    ("X-Content-Type-Options", "nosniff"),
    ("Referrer-Policy", "no-referrer"),
    ("Permissions-Policy", PERMISSIONS_POLICY),
    ("X-Frame-Options", "DENY"),
    ("Cross-Origin-Opener-Policy", "same-origin"),
    ("Cross-Origin-Resource-Policy", "same-origin"),
)


class SecurityHeadersMiddleware:
    """Sets the security headers on every HTTP response, errors and middleware refusals included.

    The strict API CSP applies everywhere except the development docs page (``/docs``), which loads the Swagger UI
    assets; docs are disabled in production. HSTS is sent in production only. ``/v1`` responses are ``no-store``.
    """

    def __init__(self, app: ASGIApp, *, production: bool, docs_path: str | None = "/docs") -> None:
        self._app = app
        self._production = production
        self._docs_path = docs_path

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        path: str = scope.get("path", "")
        docs = self._docs_path is not None and not self._production and path == self._docs_path

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers["Content-Security-Policy"] = DOCS_CSP if docs else API_CSP
                for name, value in _BASE_HEADERS:
                    headers[name] = value
                if self._production:
                    headers["Strict-Transport-Security"] = HSTS
                if path.startswith("/v1"):
                    headers["Cache-Control"] = "no-store"
            await send(message)

        await self._app(scope, receive, send_with_headers)


class BodySizeLimitMiddleware:
    """Refuses request bodies over ``max_bytes`` with a 413 problem, by ``Content-Length`` and by counting.

    The body is read before the application runs (it is small by construction) and replayed to it, so a chunked
    body without a length is refused with the same 413 instead of failing inside body parsing.
    """

    def __init__(self, app: ASGIApp, *, max_bytes: int, respond: Callable[[Scope], Awaitable[Response]]) -> None:
        self._app = app
        self._max = max_bytes
        self._respond = respond

    def _declared_length(self, scope: Scope) -> int | None:
        for name, value in scope.get("headers", []):
            if name == b"content-length":
                try:
                    return int(value)
                except ValueError:
                    return None
        return None

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        declared = self._declared_length(scope)
        if declared is not None and declared > self._max:
            await (await self._respond(scope))(scope, receive, send)
            return
        chunks: list[bytes] = []
        received = 0
        while True:
            message = await receive()
            if message["type"] != "http.request":
                await self._app(scope, _replay([message]), send)
                return
            body: bytes = message.get("body", b"")
            received += len(body)
            if received > self._max:
                await (await self._respond(scope))(scope, receive, send)
                return
            chunks.append(body)
            if not message.get("more_body", False):
                break
        buffered: Message = {"type": "http.request", "body": b"".join(chunks), "more_body": False}
        await self._app(scope, _replay([buffered], then=receive), send)


def _replay(messages: list[Message], then: Receive | None = None) -> Receive:
    """A ``receive`` that returns ``messages`` first, then defers to ``then`` (for disconnects)."""
    pending = list(messages)

    async def receive() -> Message:
        if pending:
            return pending.pop(0)
        if then is not None:
            return await then()
        return {"type": "http.disconnect"}

    return receive
