"""Maps every error onto the `ErrorEnvelope` of
[Conventions](/architecture/interfaces.md#conventions): an unknown path or a method no contract
has (`NOT_FOUND`), a declared contract not yet built
(`NOT_IMPLEMENTED`), and a malformed request body (`VALIDATION`). An unhandled exception is
caught by the outermost middleware ([`request_identity.py`](request_identity.py)) instead of a
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


def _field_from_location(location: tuple[int | str, ...]) -> str:
    """Turns a `RequestValidationError` error location into the `field` of `details.fields[]`:
    the body field name, or a JSON pointer built from the remaining parts."""
    parts = [part for part in location if part != "body"]
    if not parts:
        return "/"
    if len(parts) == 1 and isinstance(parts[0], str):
        return parts[0]
    return "/" + "/".join(str(part) for part in parts)


def register_error_handlers(app: FastAPI) -> None:
    """Registers the `NOT_FOUND`, `NOT_IMPLEMENTED` and `VALIDATION` handlers. Every other
    `HTTPException` goes to Starlette's own default handler."""

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
            {"field": _field_from_location(tuple(error["loc"])), "message": error["msg"]}
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=envelope("VALIDATION", "The input is invalid.", {"fields": fields}),
        )
