"""Request identity ([api Design](/architecture/services/api.md#design)): every request gets a
request id, bound to the log context for the lifetime of the request and returned in
`X-Request-Id`. As the outermost middleware it also catches any unhandled exception, logs it
with the request id and answers `500 INTERNAL` in the envelope — Starlette's own
`ServerErrorMiddleware` sits outside every `add_middleware` layer and would send its error
response without our header, so the catching has to happen here, not in a registered exception
handler. A plain ASGI middleware, so the request id stays bound in the same call chain
throughout, with no task boundary that could lose the context variable.
"""

from __future__ import annotations

import logging
import uuid

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from leadradar.logs import request_id_var

logger = logging.getLogger(__name__)


class RequestIdentityMiddleware:
    """Binds a fresh request id to the log context and to `X-Request-Id`; maps an unhandled
    exception onto the `INTERNAL` envelope."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        token = request_id_var.set(request_id)
        response_started = False

        async def send_with_header(message: Message) -> None:
            nonlocal response_started
            if message["type"] == "http.response.start":
                response_started = True
                headers = MutableHeaders(scope=message)
                headers.append("X-Request-Id", request_id)
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        except Exception:
            logger.exception("Unhandled exception while serving a request")
            if not response_started:
                response = JSONResponse(
                    status_code=500,
                    content={
                        "error": {"code": "INTERNAL", "message": "An unexpected error occurred."}
                    },
                    headers={"X-Request-Id": request_id},
                )
                await response(scope, receive, send)
        finally:
            request_id_var.reset(token)
