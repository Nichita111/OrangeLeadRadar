"""Maps every error onto the `ErrorEnvelope` of
[Conventions](/architecture/interfaces.md#conventions): an unknown path (`NOT_FOUND`), a method
the path does not accept (`METHOD_NOT_ALLOWED`), a declared contract not yet built
(`NOT_IMPLEMENTED`), a malformed request body or an invalid path, query or body field
(`VALIDATION`), and every typed capability error, once, at the edge
([coding Errors](/guidelines/coding.md#errors)). An unhandled exception is caught by the
outermost middleware ([`request_identity.py`](request_identity.py)) instead of a registered
handler here, because Starlette's `ServerErrorMiddleware` sits outside every layer
`add_middleware` adds and would send its response without `X-Request-Id`.
"""

from __future__ import annotations

from datetime import datetime
from http import HTTPStatus
from uuid import UUID

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import Response

from leadradar.accounts.errors import AccountNotFound, AccountValidationError, DomainConflict
from leadradar.alerts.errors import AlertNotFound
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
from leadradar.core.enums import Dependency
from leadradar.evaluation.errors import (
    ChunkNotFound,
    QuestionNotFound,
    ResultNotFound,
    RevisionNotCurrent,
    ServiceNotFound,
)
from leadradar.feedback.errors import FeedbackError
from leadradar.outreach.errors import CrmUnavailable, HubspotNotConfigured, ScoreNotFound
from leadradar.runs.errors import (
    AccountInactive,
    RefreshAccountNotFound,
    RunFinished,
    RunNotFound,
    SourcePluginNotFound,
)


class ErrorDetailField(BaseModel):
    """One entry of `details.fields[]` ([Conventions](/architecture/interfaces.md#conventions)
    `VALIDATION`)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    field: str
    message: str


class ErrorDetails(BaseModel):
    """`details` of [Conventions](/architecture/interfaces.md#conventions) `ErrorEnvelope`: the
    closed set of names the Envelope table gives. Every field is optional and, per the Naming
    paragraph (G10), absent rather than `null` when unset."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    fields: list[ErrorDetailField] | SkipJsonSchema[None] = None
    entity_id: UUID | SkipJsonSchema[None] = None
    retry_after_min: int | SkipJsonSchema[None] = None
    resets_at: datetime | SkipJsonSchema[None] = None
    dependency: Dependency | SkipJsonSchema[None] = None
    reason: str | SkipJsonSchema[None] = None


class ErrorBody(BaseModel):
    """`error` of [Conventions](/architecture/interfaces.md#conventions) `ErrorEnvelope`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    code: str
    message: str
    details: ErrorDetails | SkipJsonSchema[None] = None


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
    """The one `{"error": {"code", "message", "details"?}}` shape of
    [Conventions](/architecture/interfaces.md#conventions)."""
    body: dict[str, object] = {"code": code, "message": message}
    if details is not None:
        body["details"] = details
    return {"error": body}


def _field_name(location: tuple[int | str, ...]) -> str:
    """The `field` of a `VALIDATION` error ([Conventions](/architecture/interfaces.md#conventions)
    Envelope): a bare body field name, a JSON pointer into it, or the name of a path or query
    parameter. FastAPI's `loc` is `("body", "field", ...)`, `("path", "name")` or
    `("query", "name")`; a single string part is a bare name, anything else — several parts, none
    (a malformed body), or a single non-string part such as a malformed body's index — is a JSON
    pointer."""
    parts = location[1:]
    if len(parts) == 1 and isinstance(parts[0], str):
        return parts[0]
    return "/" + "/".join(str(part) for part in parts)


_INVALID_CREDENTIALS_MESSAGE = "Incorrect email or password."
_UNAUTHENTICATED_MESSAGE = "Sign-in required."


def register_error_handlers(app: FastAPI) -> None:
    """Registers every HTTP exception, `NOT_IMPLEMENTED`, `VALIDATION` and every typed capability
    error's handler, once, at the edge."""

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException) -> Response:
        codes = {
            401: "UNAUTHENTICATED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
            405: "METHOD_NOT_ALLOWED",
            409: "CONFLICT",
            422: "VALIDATION",
            423: "LOCKED",
            429: "BUDGET_EXHAUSTED",
            500: "INTERNAL",
            503: "UPSTREAM_UNAVAILABLE",
        }
        code = codes.get(exc.status_code, "INTERNAL")
        try:
            message = HTTPStatus(exc.status_code).phrase
        except ValueError:
            message = "HTTP error."
        if exc.status_code == 404:
            message = "The resource does not exist."
        return JSONResponse(
            status_code=exc.status_code,
            content=envelope(code, message),
            headers=exc.headers,
        )

    @app.exception_handler(ContractNotBuilt)
    async def handle_contract_not_built(request: Request, exc: ContractNotBuilt) -> Response:
        return JSONResponse(
            status_code=501,
            content=envelope("NOT_IMPLEMENTED", "This contract is declared but not built yet."),
        )

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

    @app.exception_handler(HubspotNotConfigured)
    async def handle_hubspot_not_configured(
        request: Request, exc: HubspotNotConfigured
    ) -> Response:
        return JSONResponse(status_code=409, content=envelope("NOT_CONFIGURED", str(exc)))

    @app.exception_handler(ScoreNotFound)
    async def handle_outreach_score_not_found(request: Request, exc: ScoreNotFound) -> Response:
        return JSONResponse(status_code=404, content=envelope("NOT_FOUND", str(exc)))

    @app.exception_handler(CrmUnavailable)
    async def handle_crm_unavailable(request: Request, exc: CrmUnavailable) -> Response:
        return JSONResponse(
            status_code=503,
            content=envelope(
                "UPSTREAM_UNAVAILABLE",
                "HubSpot is unavailable.",
                {"dependency": "HUBSPOT", "reason": str(exc)},
            ),
        )

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

    @app.exception_handler(AccountValidationError)
    async def handle_account_validation_error(
        request: Request, exc: AccountValidationError
    ) -> Response:
        return JSONResponse(
            status_code=422,
            content=envelope(
                "VALIDATION",
                "The input is invalid.",
                {"fields": [{"field": exc.field, "message": str(exc)}]},
            ),
        )

    @app.exception_handler(DomainConflict)
    async def handle_domain_conflict(request: Request, exc: DomainConflict) -> Response:
        return JSONResponse(
            status_code=409,
            content=envelope(
                "CONFLICT",
                str(exc),
                {"entity_id": str(exc.existing_account_id)},
            ),
        )

    @app.exception_handler(AccountNotFound)
    async def handle_account_not_found(request: Request, exc: AccountNotFound) -> Response:
        return JSONResponse(status_code=404, content=envelope("NOT_FOUND", str(exc)))

    @app.exception_handler(SourcePluginNotFound)
    async def handle_source_plugin_not_found(
        request: Request, exc: SourcePluginNotFound
    ) -> Response:
        return JSONResponse(status_code=404, content=envelope("NOT_FOUND", str(exc)))

    @app.exception_handler(AlertNotFound)
    async def handle_alert_not_found(request: Request, exc: AlertNotFound) -> Response:
        return JSONResponse(status_code=404, content=envelope("NOT_FOUND", str(exc)))

    @app.exception_handler(ServiceNotFound)
    @app.exception_handler(ChunkNotFound)
    @app.exception_handler(QuestionNotFound)
    @app.exception_handler(ResultNotFound)
    async def handle_evaluation_not_found(request: Request, exc: Exception) -> Response:
        return JSONResponse(status_code=404, content=envelope("NOT_FOUND", str(exc)))

    @app.exception_handler(RevisionNotCurrent)
    async def handle_revision_not_current(request: Request, exc: RevisionNotCurrent) -> Response:
        return JSONResponse(status_code=409, content=envelope("CONFLICT", str(exc)))
