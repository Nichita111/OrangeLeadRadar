"""Maps an unknown path onto the `NOT_FOUND` envelope of
[Conventions](/architecture/interfaces.md#conventions). An unhandled exception is caught by the
outermost middleware ([`request_identity.py`](request_identity.py)) instead of a registered
handler here, because Starlette's `ServerErrorMiddleware` sits outside every layer `add_middleware`
adds and would send its response without `X-Request-Id`. No other code is mapped yet.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _envelope(code: str, message: str) -> dict[str, object]:
    return {"error": {"code": code, "message": message}}


def register_error_handlers(app: FastAPI) -> None:
    """Registers the `NOT_FOUND` handler for an unknown path."""

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        if exc.status_code == 404:
            return JSONResponse(
                status_code=404, content=_envelope("NOT_FOUND", "The resource does not exist.")
            )
        return JSONResponse(
            status_code=exc.status_code, content=_envelope("INTERNAL", str(exc.detail))
        )
