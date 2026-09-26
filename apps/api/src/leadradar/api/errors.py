"""Maps every error onto the `ErrorEnvelope` of
[Conventions](/architecture/interfaces.md#conventions): an unknown path or a method no contract
has (`NOT_FOUND`), a declared contract not yet built (`NOT_IMPLEMENTED`), a malformed request
body or an invalid path, query or body field (`VALIDATION`), and the typed errors `auth.sessions`
and `feedback.errors` raise (`UNAUTHENTICATED`, `FORBIDDEN`, `NOT_FOUND`). An unhandled exception
is caught by the outermost middleware ([`request_identity.py`](request_identity.py)) instead of a
registered handler here, because Starlette's `ServerErrorMiddleware` sits outside every layer
`add_middleware` adds and would send its response without `X-Request-Id`.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from leadradar.auth.sessions import Forbidden, Unauthenticated
from leadradar.feedback.errors import FeedbackError


class ErrorBody(BaseModel):
    """`error` of [Conventions](/architecture/interfaces.md#conventions) `ErrorEnvelope`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    details: dict[str, object] | None = None


class ErrorEnvelope(BaseModel):
    """The `{"error": {...}}` shape of [Conventions](/architecture/interfaces.md#conventions),
    named `ErrorEnvelope` in the OpenAPI document."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    error: ErrorBody


class ContractNotBuilt(Exception):
    """Raised by [`contract_not_built`](not_built.py) for a declared contract whose feature is
    not built yet; mapped onto `501 NOT_IMPLEMENTED`
    ([Conventions](/architecture/interfaces.md#conventions))."""


def envelope(
    code: str, message: str, details: dict[str, object] | None = None
) -> dict[str, object]:
    """The `ErrorEnvelope` shape of [Conventions](/architecture/interfaces.md#conventions)."""
    body: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


def _field_name(location: tuple[int | str, ...]) -> str:
    """The `field` of a `VALIDATION` error ([Conventions](/architecture/interfaces.md#conventions)
    Envelope): a bare body field name, a JSON pointer into it, or the name of a path or query
    parameter. FastAPI's `loc` is `("body", "field", ...)`, `("path", "name")` or
    `("query", "name")`; a single remaining part is a bare name, several are a JSON pointer."""
    parts = [str(part) for part in location[1:]]
    if len(parts) <= 1:
        return parts[0] if parts else str(location[-1])
    return "/" + "/".join(parts)


def register_error_handlers(app: FastAPI) -> None:
    """Registers the `NOT_FOUND`, `NOT_IMPLEMENTED`, `VALIDATION` and typed-error handlers. Every
    other `HTTPException` goes to Starlette's own default handler."""

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code in (404, 405):
            return JSONResponse(
                status_code=404, content=envelope("NOT_FOUND", "The resource does not exist.")
            )
        return await http_exception_handler(request, exc)

    @app.exception_handler(ContractNotBuilt)
    async def handle_contract_not_built(request: Request, exc: ContractNotBuilt) -> Response:
        return JSONResponse(
            status_code=501,
            content=envelope("NOT_IMPLEMENTED", "This contract is declared but not built yet."),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> Response:
        fields = [
            {"field": _field_name(tuple(error["loc"])), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=envelope("VALIDATION", "The input is invalid.", {"fields": fields}),
        )

    @app.exception_handler(Unauthenticated)
    async def handle_unauthenticated(request: Request, exc: Unauthenticated) -> Response:
        return JSONResponse(status_code=401, content=envelope("UNAUTHENTICATED", str(exc)))

    @app.exception_handler(Forbidden)
    async def handle_forbidden(request: Request, exc: Forbidden) -> Response:
        return JSONResponse(status_code=403, content=envelope("FORBIDDEN", str(exc)))

    @app.exception_handler(FeedbackError)
    async def handle_feedback_error(request: Request, exc: FeedbackError) -> Response:
        return JSONResponse(status_code=404, content=envelope("NOT_FOUND", str(exc)))
