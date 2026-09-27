"""Contract tests of `API-46` `POST /api/v1/accounts/{id}/scores/{service_id}/feedback` and
`API-47` `POST /api/v1/findings/{id}/feedback`
([Feedback and alerts](/architecture/interfaces.md#feedback-and-alerts)).

Every test but the authentication and CSRF ones overrides `get_session` and `current_user` and
monkeypatches the capability function, as `test_evaluation_contract.py` does. The authentication
and CSRF tests run the real dependency and middleware, so no override touches them."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI

from leadradar.api.authentication import current_user
from leadradar.auth.sessions import Principal
from leadradar.core.enums import (
    AppUserRole,
    DocumentSourceType,
    FindingDecidedBy,
    FindingFeedbackVerdict,
    FindingStatus,
    FindingStrength,
    LeadFeedbackVerdict,
    SignalQuestionPolarity,
    SourcePluginCode,
)
from leadradar.core.impact import ImpactReport
from leadradar.db.session import get_session
from leadradar.feedback.errors import FindingNotFound, ScoreNotFound
from leadradar.feedback.queries import (
    DocumentSummary,
    FeedbackSummary,
    FindingViewData,
    LeadFeedbackResult,
    QuestionSummary,
)

pytestmark = pytest.mark.contract

_NOW = datetime(2026, 1, 15, tzinfo=UTC)
_CSRF_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def _principal(role: AppUserRole = AppUserRole.SALES) -> Principal:
    return Principal(user_id=uuid.uuid4(), display_name="Ada Lovelace", role=role)


def _override(app: FastAPI, principal: Principal) -> None:
    app.dependency_overrides[get_session] = lambda: None
    app.dependency_overrides[current_user] = lambda: principal


def _clear(app: FastAPI) -> None:
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(current_user, None)


def _lead_feedback_result(principal: Principal) -> LeadFeedbackResult:
    return LeadFeedbackResult(
        id=uuid.uuid4(),
        verdict=LeadFeedbackVerdict.RELEVANT,
        note="a note",
        created_at=_NOW,
        user_name=principal.display_name,
    )


def _finding_view(principal: Principal) -> FindingViewData:
    return FindingViewData(
        id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        question=QuestionSummary(
            id=uuid.uuid4(),
            key="A_QUESTION",
            text="Does it?",
            polarity=SignalQuestionPolarity.POSITIVE,
        ),
        question_revision=1,
        confidence=0.7,
        quote="a quote",
        quote_en=None,
        rationale="a rationale",
        observed_at=_NOW,
        strength=FindingStrength.STRONG,
        decided_by=FindingDecidedBy.LLM,
        status=FindingStatus.REJECTED,
        option=None,
        document=DocumentSummary(
            id=uuid.uuid4(),
            title="A title",
            url="https://example.com/a",
            source_type=DocumentSourceType.NEWS,
            plugin_code=SourcePluginCode.GDELT,
            language="en",
            published_at=None,
        ),
        points=12.5,
        feedback=FeedbackSummary(
            verdict=FindingFeedbackVerdict.WRONG, user_name=principal.display_name, created_at=_NOW
        ),
    )


def _lead_feedback_url(account_id: object = None, service_id: object = None) -> str:
    account = account_id or uuid.uuid4()
    service = service_id or uuid.uuid4()
    return f"/api/v1/accounts/{account}/scores/{service}/feedback"


def _finding_feedback_url(finding_id: object = None) -> str:
    return f"/api/v1/findings/{finding_id or uuid.uuid4()}/feedback"


# --- API-46 -------------------------------------------------------------------------------


async def test_lead_feedback_answers_200_with_exactly_lead_feedbacks_fields(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    principal = _principal()
    result = _lead_feedback_result(principal)

    async def fake_give_lead_feedback(*args: object, **kwargs: object) -> LeadFeedbackResult:
        return result

    monkeypatch.setattr(
        "leadradar.api.feedback_and_alerts.give_lead_feedback", fake_give_lead_feedback
    )
    _override(app, principal)

    response = await client.post(
        _lead_feedback_url(), json={"verdict": "RELEVANT"}, headers=_CSRF_HEADERS
    )

    _clear(app)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"id", "verdict", "note", "created_at", "user_name"}
    assert body["verdict"] == "RELEVANT"
    assert body["user_name"] == principal.display_name


@pytest.mark.parametrize(
    ("payload", "field"),
    [
        ({"verdict": "WRONG"}, "verdict"),
        ({}, "verdict"),
        ({"verdict": "RELEVANT", "extra": "not allowed"}, "extra"),
    ],
)
async def test_lead_feedback_refuses_an_invalid_body_with_422_validation(
    app: FastAPI, client: httpx.AsyncClient, payload: dict[str, object], field: str
) -> None:
    _override(app, _principal())

    response = await client.post(_lead_feedback_url(), json=payload, headers=_CSRF_HEADERS)

    _clear(app)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION"
    assert any(entry["field"] == field for entry in body["error"]["details"]["fields"])


async def test_lead_feedback_answers_404_not_found_when_the_score_is_not_found(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_give_lead_feedback(*args: object, **kwargs: object) -> LeadFeedbackResult:
        raise ScoreNotFound("No current score.")

    monkeypatch.setattr(
        "leadradar.api.feedback_and_alerts.give_lead_feedback", fake_give_lead_feedback
    )
    _override(app, _principal())

    response = await client.post(
        _lead_feedback_url(), json={"verdict": "RELEVANT"}, headers=_CSRF_HEADERS
    )

    _clear(app)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- API-47 -------------------------------------------------------------------------------


async def test_finding_feedback_answers_200_with_exactly_finding_views_fields(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    principal = _principal()
    view = _finding_view(principal)

    async def fake_give_finding_feedback(*args: object, **kwargs: object) -> FindingViewData:
        return view

    monkeypatch.setattr(
        "leadradar.api.feedback_and_alerts.give_finding_feedback", fake_give_finding_feedback
    )
    _override(app, principal)

    response = await client.post(
        _finding_feedback_url(), json={"verdict": "WRONG"}, headers=_CSRF_HEADERS
    )

    _clear(app)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "id",
        "account_id",
        "service_id",
        "question",
        "question_revision",
        "confidence",
        "quote",
        "quote_en",
        "rationale",
        "observed_at",
        "strength",
        "decided_by",
        "status",
        "option",
        "document",
        "points",
        "feedback",
    }
    assert set(body["feedback"].keys()) == {"verdict", "user_name", "created_at"}


async def test_finding_feedback_refuses_already_customer_with_422_validation(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    _override(app, _principal())

    response = await client.post(
        _finding_feedback_url(), json={"verdict": "ALREADY_CUSTOMER"}, headers=_CSRF_HEADERS
    )

    _clear(app)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION"


async def test_finding_feedback_answers_404_not_found_when_the_finding_is_not_found(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_give_finding_feedback(*args: object, **kwargs: object) -> FindingViewData:
        raise FindingNotFound("No such finding.")

    monkeypatch.setattr(
        "leadradar.api.feedback_and_alerts.give_finding_feedback", fake_give_finding_feedback
    )
    _override(app, _principal())

    response = await client.post(
        _finding_feedback_url(), json={"verdict": "WRONG"}, headers=_CSRF_HEADERS
    )

    _clear(app)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


# --- shared: malformed path ids, authentication, CSRF, roles --------------------------------


@pytest.mark.parametrize(
    ("url", "field"),
    [
        (f"/api/v1/accounts/not-a-uuid/scores/{uuid.uuid4()}/feedback", "id"),
        (f"/api/v1/accounts/{uuid.uuid4()}/scores/not-a-uuid/feedback", "service_id"),
        ("/api/v1/findings/not-a-uuid/feedback", "id"),
    ],
)
async def test_a_malformed_path_id_answers_422_validation_naming_the_parameter(
    app: FastAPI, client: httpx.AsyncClient, url: str, field: str
) -> None:
    _override(app, _principal())

    response = await client.post(url, json={"verdict": "RELEVANT"}, headers=_CSRF_HEADERS)

    _clear(app)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION"
    assert any(entry["field"] == field for entry in body["error"]["details"]["fields"])


@pytest.mark.parametrize("url", [_lead_feedback_url(), _finding_feedback_url()])
async def test_both_routes_answer_401_unauthenticated_without_the_session_cookie(
    client: httpx.AsyncClient, url: str
) -> None:
    response = await client.post(url, json={"verdict": "RELEVANT"}, headers=_CSRF_HEADERS)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert response.headers.get("x-request-id")


@pytest.mark.parametrize("url", [_lead_feedback_url(), _finding_feedback_url()])
async def test_both_routes_answer_403_forbidden_without_the_csrf_header(
    client: httpx.AsyncClient, url: str
) -> None:
    response = await client.post(url, json={"verdict": "RELEVANT"})

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert response.headers.get("x-request-id")


@pytest.mark.parametrize("role", [AppUserRole.SALES, AppUserRole.ADMIN])
async def test_lead_feedback_admits_both_roles(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, role: AppUserRole
) -> None:
    principal = _principal(role)

    async def fake_give_lead_feedback(*args: object, **kwargs: object) -> LeadFeedbackResult:
        return _lead_feedback_result(principal)

    monkeypatch.setattr(
        "leadradar.api.feedback_and_alerts.give_lead_feedback", fake_give_lead_feedback
    )
    _override(app, principal)

    response = await client.post(
        _lead_feedback_url(), json={"verdict": "RELEVANT"}, headers=_CSRF_HEADERS
    )

    _clear(app)
    assert response.status_code == 200


@pytest.mark.parametrize("role", [AppUserRole.SALES, AppUserRole.ADMIN])
async def test_finding_feedback_admits_both_roles(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, role: AppUserRole
) -> None:
    principal = _principal(role)

    async def fake_give_finding_feedback(*args: object, **kwargs: object) -> FindingViewData:
        return _finding_view(principal)

    monkeypatch.setattr(
        "leadradar.api.feedback_and_alerts.give_finding_feedback", fake_give_finding_feedback
    )
    _override(app, principal)

    response = await client.post(
        _finding_feedback_url(), json={"verdict": "WRONG"}, headers=_CSRF_HEADERS
    )

    _clear(app)
    assert response.status_code == 200


async def test_health_and_impact_still_answer_without_the_csrf_header(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from leadradar.audit.health import HealthCheckStatus, HealthResult, HealthStatus

    async def fake_read_health(*args: object, **kwargs: object) -> HealthResult:
        return HealthResult(
            status=HealthStatus.OK,
            checks={
                "database": HealthCheckStatus.OK,
                "embedder": HealthCheckStatus.OK,
                "classifier": HealthCheckStatus.OK,
                "llm": HealthCheckStatus.OK,
            },
        )

    monkeypatch.setattr("leadradar.api.audit_and_health.read_health", fake_read_health)

    async def fake_read_impact(*args: object, **kwargs: object) -> ImpactReport:
        return ImpactReport(
            period_days=30,
            accounts_refreshed=0,
            refreshes=0,
            cost_per_refresh_eur=None,
            minutes_per_refresh=None,
            findings_created=0,
            precision=None,
            labelled_items=None,
            manual_minutes_per_account=120,
            manual_hours_replaced=0.0,
        )

    monkeypatch.setattr("leadradar.api.evaluation.read_impact", fake_read_impact)
    app.dependency_overrides[get_session] = lambda: None

    health_response = await client.get("/api/v1/health")
    impact_response = await client.get("/api/v1/impact")

    app.dependency_overrides.pop(get_session, None)
    assert health_response.status_code == 200
    assert impact_response.status_code == 200
