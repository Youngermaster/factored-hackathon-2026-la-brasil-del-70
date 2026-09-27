"""RFC 9457 problem details: the single place where errors become HTTP responses.

Handlers never leak internal details. Validation problems list the location and error type of each
invalid field, never the rejected input. Unexpected exceptions are logged server-side and returned as a
generic 500.

Typed errors from inner layers are mapped with ``ProblemRegistry.register``; phase 02 registers the
domain errors here, so no router formats errors itself.
"""

from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from typing import Any, Final

import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

PROBLEM_CONTENT_TYPE: Final = "application/problem+json"
PROBLEM_TYPE_BASE: Final = "https://bank-agent.local/problems/"

_logger = structlog.get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ProblemType:
    """How one exception type is presented to clients."""

    status: int
    slug: str
    title: str

    @property
    def type_uri(self) -> str:
        return f"{PROBLEM_TYPE_BASE}{self.slug}"


VALIDATION_PROBLEM: Final = ProblemType(422, "validation-error", "Request validation failed")
INTERNAL_PROBLEM: Final = ProblemType(HTTPStatus.INTERNAL_SERVER_ERROR, "internal-error", "Internal server error")
PAYLOAD_TOO_LARGE_PROBLEM: Final = ProblemType(413, "payload-too-large", "The request body is too large")

HeaderFactory = Callable[[Exception], dict[str, str]]


def problem_response(
    problem: ProblemType,
    request: Request,
    detail: str | None = None,
    extensions: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """Build an ``application/problem+json`` response for ``problem``."""
    body: dict[str, Any] = {
        "type": problem.type_uri,
        "title": problem.title,
        "status": problem.status,
        "instance": request.url.path,
    }
    if detail is not None:
        body["detail"] = detail
    request_id = getattr(request.state, "request_id", None)
    if request_id is not None:
        body["request_id"] = request_id
    if extensions:
        body.update(extensions)
    return JSONResponse(body, status_code=problem.status, media_type=PROBLEM_CONTENT_TYPE, headers=headers)


def _http_problem(status_code: int) -> ProblemType:
    try:
        status = HTTPStatus(status_code)
    except ValueError:
        return ProblemType(status_code, "http-error", "HTTP error")
    return ProblemType(status_code, status.phrase.lower().replace(" ", "-").replace("'", ""), status.phrase)


class ProblemRegistry:
    """Maps exception types to problem types and installs the handlers on an application."""

    def __init__(self) -> None:
        self._problems: dict[type[Exception], ProblemType] = {}
        self._headers: dict[type[Exception], HeaderFactory] = {}

    def register(
        self, exception_type: type[Exception], problem: ProblemType, headers: HeaderFactory | None = None
    ) -> None:
        """Present ``exception_type`` (and its subclasses) as ``problem``. Its message is never exposed.

        ``headers`` builds response headers from the exception, for example ``Retry-After``.
        """
        if exception_type in self._problems:
            raise ValueError(f"a problem type is already registered for {exception_type.__name__}")
        self._problems[exception_type] = problem
        if headers is not None:
            self._headers[exception_type] = headers

    def _headers_for(self, exception: Exception) -> dict[str, str] | None:
        for klass in type(exception).__mro__:
            if klass in self._problems:
                factory = self._headers.get(klass)
                return factory(exception) if factory is not None else None
        return None

    @property
    def problem_types(self) -> tuple[ProblemType, ...]:
        """Every registered problem type, in registration order, without duplicates."""
        return tuple(dict.fromkeys(self._problems.values()))

    def problem_for(self, exception: Exception) -> ProblemType | None:
        """Return the problem for the most specific registered base class of ``exception``."""
        for klass in type(exception).__mro__:
            problem = self._problems.get(klass)
            if problem is not None:
                return problem
        return None

    def install(self, app: FastAPI) -> None:
        """Install the exception handlers on ``app``."""
        app.add_exception_handler(StarletteHTTPException, self._handle_http_exception)  # type: ignore[arg-type]
        app.add_exception_handler(RequestValidationError, self._handle_validation_error)  # type: ignore[arg-type]
        for exception_type in self._problems:
            app.add_exception_handler(exception_type, self._handle_registered)
        app.add_exception_handler(Exception, self._handle_unexpected)

    async def _handle_http_exception(self, request: Request, exc: StarletteHTTPException) -> JSONResponse:
        problem = _http_problem(exc.status_code)
        headers = dict(exc.headers) if exc.headers else None
        detail = exc.detail if isinstance(exc.detail, str) and exc.detail != problem.title else None
        return problem_response(problem, request, detail=detail, headers=headers)

    async def _handle_validation_error(self, request: Request, exc: RequestValidationError) -> JSONResponse:
        errors = [
            {"loc": [str(part) for part in error.get("loc", ())], "type": str(error.get("type", "invalid"))}
            for error in exc.errors()
        ]
        return problem_response(VALIDATION_PROBLEM, request, extensions={"errors": errors})

    async def _handle_registered(self, request: Request, exc: Exception) -> JSONResponse:
        problem = self.problem_for(exc)
        if problem is None:
            return await self._handle_unexpected(request, exc)
        return problem_response(problem, request, headers=self._headers_for(exc))

    async def _handle_unexpected(self, request: Request, exc: Exception) -> JSONResponse:
        _logger.error(
            "unhandled_exception",
            path=request.url.path,
            request_id=getattr(request.state, "request_id", None),
            exc_info=exc,
        )
        return problem_response(INTERNAL_PROBLEM, request)
