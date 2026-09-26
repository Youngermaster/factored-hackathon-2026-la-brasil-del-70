"""Pure ASGI middleware."""

import re
from collections.abc import Callable
from typing import Final

import structlog
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

REQUEST_ID_HEADER: Final = "X-Request-ID"
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
