"""CSRF ([Conventions](/architecture/interfaces.md#conventions) CSRF, G6 (a)): a `POST`, `PUT`,
`PATCH` or `DELETE` without an `X-Requested-With` header is refused `403 FORBIDDEN`.

A plain ASGI middleware, like [`RequestIdentityMiddleware`](request_identity.py), and for the
same reason: `api/app.py` adds it before `RequestIdentityMiddleware`, so it sits inside that
layer and a refusal still carries `X-Request-Id` and the one request log line. It answers
directly instead of raising, because it sits outside FastAPI's own routing and exception
handling and a raised exception there would otherwise surface as `500 INTERNAL`."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from leadradar.api.errors import envelope

_STATE_CHANGING_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class CsrfMiddleware:
    """Refuses a state-changing request that carries no `X-Requested-With` header."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in _STATE_CHANGING_METHODS:
            await self.app(scope, receive, send)
            return

        headers = dict(scope["headers"])
        if b"x-requested-with" not in headers:
            response = JSONResponse(
                status_code=403,
                content=envelope("FORBIDDEN", "This request is missing the CSRF header."),
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
