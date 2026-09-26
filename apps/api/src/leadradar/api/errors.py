"""Maps an unknown path onto the `NOT_FOUND` envelope of
[Conventions](/architecture/interfaces.md#conventions). An unhandled exception is caught by the
outermost middleware ([`request_identity.py`](request_identity.py)) instead of a registered
handler here, because Starlette's `ServerErrorMiddleware` sits outside every layer `add_middleware`
adds and would send its response without `X-Request-Id`. No other code is mapped yet.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response


def envelope(code: str, message: str) -> dict[str, object]:
    """The one `{"error": {"code", "message"}}` shape of
    [Conventions](/architecture/interfaces.md#conventions)."""
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    """Registers the `NOT_FOUND` handler for an unknown path. Every other `HTTPException`
    goes to Starlette's own default handler: "No other codes are mapped yet" (design)."""

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 404:
            return JSONResponse(
                status_code=404, content=envelope("NOT_FOUND", "The resource does not exist.")
            )
        # When the detail is already an envelope dict, pass it through directly
        # so the response body is {"error": {...}} per the Conventions contract.
        if isinstance(exc.detail, dict) and "error" in exc.detail:
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        return await http_exception_handler(request, exc)
