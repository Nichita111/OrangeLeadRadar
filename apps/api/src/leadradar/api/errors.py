"""Maps every typed error onto the envelope of
[Conventions](/architecture/interfaces.md#conventions), once, at the edge
([coding Errors](/guidelines/coding.md#errors)). An unhandled exception is caught by the
outermost middleware ([`request_identity.py`](request_identity.py)) instead of a registered
handler here, because Starlette's `ServerErrorMiddleware` sits outside every layer `add_middleware`
adds and would send its response without `X-Request-Id`.
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from leadradar.auth.errors import (
    AccountDisabled,
    AccountLocked,
    EmailTaken,
    Forbidden,
    InvalidCredentials,
    PasswordTooShort,
    SelfChangeRefused,
    Unauthenticated,
    UserNotFound,
)
from leadradar.configuration.errors import Conflict, DraftInvalid, NotFound, QuestionInvalid
from leadradar.feedback.errors import FeedbackError
from leadradar.runs.errors import (
    AccountInactive,
    RefreshAccountNotFound,
    RunFinished,
    RunNotFound,
)


def envelope(
    code: str, message: str, details: dict[str, object] | None = None
) -> dict[str, object]:
    """The one `{"error": {"code", "message", "details"?}}` shape of
    [Conventions](/architecture/interfaces.md#conventions)."""
    error: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"error": error}


def _field_name(location: tuple[int | str, ...]) -> str:
    """The `field` of a `VALIDATION` error ([Conventions](/architecture/interfaces.md#conventions)
    Envelope): a bare body field name, a JSON pointer into it, or the name of a path or query
    parameter. FastAPI's `loc` is `("body", "field", ...)`, `("path", "name")` or
    `("query", "name")`; a single remaining part is a bare name, several are a JSON pointer."""
    parts = [str(part) for part in location[1:]]
    if len(parts) <= 1:
        return parts[0] if parts else str(location[-1])
    return "/" + "/".join(parts)


_INVALID_CREDENTIALS_MESSAGE = "Incorrect email or password."
_UNAUTHENTICATED_MESSAGE = "Sign-in required."


def register_error_handlers(app: FastAPI) -> None:
    """Registers every typed capability error and `RequestValidationError`; every other
    `HTTPException` (only `404` today) goes to Starlette's own default handler."""

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> Response:
        if exc.status_code == 404:
            return JSONResponse(
                status_code=404, content=envelope("NOT_FOUND", "The resource does not exist.")
            )
        return await http_exception_handler(request, exc)

    @app.exception_handler(InvalidCredentials)
    async def handle_invalid_credentials(request: Request, exc: InvalidCredentials) -> Response:
        return JSONResponse(
            status_code=401, content=envelope("UNAUTHENTICATED", _INVALID_CREDENTIALS_MESSAGE)
        )

    @app.exception_handler(Unauthenticated)
    async def handle_unauthenticated(request: Request, exc: Unauthenticated) -> Response:
        return JSONResponse(
            status_code=401, content=envelope("UNAUTHENTICATED", _UNAUTHENTICATED_MESSAGE)
        )

    @app.exception_handler(Forbidden)
    @app.exception_handler(AccountDisabled)
    async def handle_forbidden(request: Request, exc: Exception) -> Response:
        return JSONResponse(
            status_code=403, content=envelope("FORBIDDEN", "Not allowed for this account.")
        )

    @app.exception_handler(UserNotFound)
    async def handle_user_not_found(request: Request, exc: UserNotFound) -> Response:
        return JSONResponse(
            status_code=404, content=envelope("NOT_FOUND", "The resource does not exist.")
        )

    @app.exception_handler(EmailTaken)
    async def handle_email_taken(request: Request, exc: EmailTaken) -> Response:
        return JSONResponse(
            status_code=409,
            content=envelope(
                "CONFLICT", "Email already in use.", {"entity_id": str(exc.entity_id)}
            ),
        )

    @app.exception_handler(SelfChangeRefused)
    async def handle_self_change_refused(request: Request, exc: SelfChangeRefused) -> Response:
        return JSONResponse(
            status_code=409,
            content=envelope("CONFLICT", "An Admin cannot change their own role or status."),
        )

    @app.exception_handler(AccountLocked)
    async def handle_account_locked(request: Request, exc: AccountLocked) -> Response:
        return JSONResponse(
            status_code=423,
            content=envelope(
                "LOCKED", "Too many failed sign-ins.", {"retry_after_min": exc.retry_after_min}
            ),
        )

    @app.exception_handler(PasswordTooShort)
    async def handle_password_too_short(request: Request, exc: PasswordTooShort) -> Response:
        return JSONResponse(
            status_code=422,
            content=envelope(
                "VALIDATION",
                "The input is invalid.",
                {
                    "fields": [
                        {
                            "field": "password",
                            "message": (f"String should have at least {exc.minimum} characters"),
                        }
                    ]
                },
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> Response:
        # Pydantic's `input` and `ctx` are dropped: they can carry the submitted value (for
        # example a password), which must never reach a response or a log (N-07).
        fields = [
            {
                "field": _field_name(tuple(error["loc"])),
                "message": error["msg"],
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=envelope("VALIDATION", "The input is invalid.", {"fields": fields}),
        )

    @app.exception_handler(FeedbackError)
    async def handle_feedback_error(request: Request, exc: FeedbackError) -> Response:
        return JSONResponse(status_code=404, content=envelope("NOT_FOUND", str(exc)))

    @app.exception_handler(RunNotFound)
    @app.exception_handler(RefreshAccountNotFound)
    async def handle_run_not_found(request: Request, exc: Exception) -> Response:
        return JSONResponse(
            status_code=404, content=envelope("NOT_FOUND", "The resource does not exist.")
        )

    @app.exception_handler(NotFound)
    async def handle_configuration_not_found(request: Request, exc: NotFound) -> Response:
        return JSONResponse(
            status_code=404, content=envelope("NOT_FOUND", "The resource does not exist.")
        )

    @app.exception_handler(AccountInactive)
    async def handle_account_inactive(request: Request, exc: AccountInactive) -> Response:
        return JSONResponse(
            status_code=409, content=envelope("CONFLICT", "The account is inactive.")
        )

    @app.exception_handler(RunFinished)
    async def handle_run_finished(request: Request, exc: RunFinished) -> Response:
        return JSONResponse(
            status_code=409, content=envelope("CONFLICT", "The run has already finished.")
        )

    @app.exception_handler(Conflict)
    async def handle_configuration_conflict(request: Request, exc: Conflict) -> Response:
        return JSONResponse(
            status_code=409,
            content=envelope("CONFLICT", str(exc), {"entity_id": exc.entity_id}),
        )

    @app.exception_handler(DraftInvalid)
    async def handle_draft_invalid(request: Request, exc: DraftInvalid) -> Response:
        return JSONResponse(
            status_code=422,
            content=envelope(
                "VALIDATION",
                "The input is invalid.",
                {"fields": [{"field": e.field, "message": e.message} for e in exc.fields]},
            ),
        )

    @app.exception_handler(QuestionInvalid)
    async def handle_question_invalid(request: Request, exc: QuestionInvalid) -> Response:
        return JSONResponse(
            status_code=422,
            content=envelope(
                "VALIDATION",
                "The input is invalid.",
                {"fields": [{"field": e.field, "message": e.message} for e in exc.fields]},
            ),
        )
