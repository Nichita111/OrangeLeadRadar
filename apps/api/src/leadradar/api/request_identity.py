"""Request identity ([api Design](/architecture/services/api.md#design)): every request gets a
request id, bound to the log context for the lifetime of the request and returned in
`X-Request-Id`. As the outermost middleware it also catches any unhandled exception, logs it
with the request id and answers `500 INTERNAL` in the envelope — Starlette's own
`ServerErrorMiddleware` sits outside every `add_middleware` layer and would send its error
response without our header, so the catching has to happen here, not in a registered exception
handler. A plain ASGI middleware, so the request id stays bound in the same call chain
throughout, with no task boundary that could lose the context variable.

It also writes one request line per served request (`method`, `path`, `status`, `duration_ms`),
written in the `finally` block before the request id is unbound, so it carries `request_id`.
`path` is the ASGI path, without the query string. A request whose response never started (for
example a disconnected client) is not a served request and writes no line. `design.md` lists
this under **Not building** ("a request access log"); the human's decision in `task.md`
(2026-09-26, "Critic R-2 (per-request log line): keep it") keeps it anyway, because it is what
makes `N-12` observable and what QA's `AC-67` test relies on, while Uvicorn's own access log
stays off.
"""

from __future__ import annotations

import logging
import time
import uuid

from starlette.datastructures import MutableHeaders
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from leadradar.api.errors import envelope
from leadradar.logs import request_id_var

logger = logging.getLogger(__name__)


class RequestIdentityMiddleware:
    """Binds a fresh request id to the log context and to `X-Request-Id`; maps an unhandled
    exception onto the `INTERNAL` envelope; writes the one request line per served request."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = str(uuid.uuid4())
        token = request_id_var.set(request_id)
        response_started = False
        status_code = 0
        started_at = time.perf_counter()

        async def send_with_header(message: Message) -> None:
            nonlocal response_started, status_code
            if message["type"] == "http.response.start":
                response_started = True
                status_code = message["status"]
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
                    content=envelope("INTERNAL", "An unexpected error occurred."),
                )
                await response(scope, receive, send_with_header)
        finally:
            if response_started:
                duration_ms = (time.perf_counter() - started_at) * 1000
                logger.info(
                    "Served request",
                    extra={
                        "method": scope["method"],
                        "path": scope["path"],
                        "status": status_code,
                        "duration_ms": duration_ms,
                    },
                )
            request_id_var.reset(token)
