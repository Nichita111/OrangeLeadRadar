"""CSRF check ([Conventions](/architecture/interfaces.md#conventions) CSRF, `S-SEC-02`): a
`POST`, `PUT`, `PATCH` or `DELETE` without an `X-Requested-With` header is refused `403 FORBIDDEN`
before routing or authentication, so an anonymous request and a request to an unknown path get
the same answer. Added inside `RequestIdentityMiddleware` so its response still carries
`X-Request-Id` and is written to the request log line."""

from __future__ import annotations

from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from leadradar.api.errors import envelope

_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class CsrfMiddleware:
    """Refuses every unsafe method without `X-Requested-With`."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        if scope["method"] in _UNSAFE_METHODS and not any(
            name == b"x-requested-with" for name, _value in scope["headers"]
        ):
            response = JSONResponse(
                status_code=403,
                content=envelope("FORBIDDEN", "Missing the X-Requested-With header."),
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)
