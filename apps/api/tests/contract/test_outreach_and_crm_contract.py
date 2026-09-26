"""Contract tests of `API-59` `POST /api/v1/accounts/{id}/scores/{service_id}/crm-push`
([Outreach and CRM](/architecture/interfaces.md#outreach-and-crm), `AC-51` half (a)).

Every test but the authentication and CSRF ones overrides `get_session` and `current_user` and
monkeypatches the capability function, as `test_feedback_and_alerts_contract.py` does. The
`409 NOT_CONFIGURED` tests run the real `push_to_crm` against an overridden `ApiSettings` with
no token, since the token check happens before any session use."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import FastAPI

from leadradar.api.authentication import current_user
from leadradar.auth.sessions import Principal
from leadradar.core.enums import AppUserRole, CrmSyncStatus, CrmSyncTarget
from leadradar.db.session import get_session
from leadradar.outreach.errors import CrmUnavailable, ScoreNotFound
from leadradar.outreach.queries import CrmSyncResult

pytestmark = pytest.mark.contract

_NOW = datetime(2026, 1, 15, tzinfo=UTC)
_CSRF_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def _principal(role: AppUserRole = AppUserRole.SALES) -> Principal:
    return Principal(user_id=uuid.uuid4(), display_name="Ada Lovelace", role=role)


def _crm_push_url(account_id: object = None, service_id: object = None) -> str:
    account = account_id or uuid.uuid4()
    service = service_id or uuid.uuid4()
    return f"/api/v1/accounts/{account}/scores/{service}/crm-push"


def _override(app: FastAPI, principal: Principal) -> None:
    app.dependency_overrides[get_session] = lambda: None
    app.dependency_overrides[current_user] = lambda: principal


def _clear(app: FastAPI) -> None:
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(current_user, None)


def _crm_sync_result() -> CrmSyncResult:
    return CrmSyncResult(
        id=uuid.uuid4(),
        external_id="hubspot-company-1",
        error=None,
        created_at=_NOW,
        target=CrmSyncTarget.HUBSPOT,
        status=CrmSyncStatus.SUCCEEDED,
    )


async def test_a_successful_push_answers_the_exact_crm_sync_view_fields(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    result = _crm_sync_result()

    async def fake_push_to_crm(*args: object, **kwargs: object) -> CrmSyncResult:
        return result

    monkeypatch.setattr("leadradar.api.outreach_and_crm.push_to_crm", fake_push_to_crm)
    _override(app, _principal())

    response = await client.post(_crm_push_url(), headers=_CSRF_HEADERS)

    _clear(app)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {"id", "external_id", "error", "created_at", "target", "status"}
    assert body["target"] == "HUBSPOT"
    assert body["status"] == "SUCCEEDED"
    assert body["external_id"] == "hubspot-company-1"


async def test_answers_409_not_configured_when_the_token_is_unset_and_nothing_is_pushed(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    """Runs the real `push_to_crm` against the fixture's default `ApiSettings`, which has no
    `hubspot_access_token`: the token check raises before any session use, so overriding
    `get_session` with `None` is safe (`AC-51` half (a))."""
    _override(app, _principal())

    response = await client.post(_crm_push_url(), headers=_CSRF_HEADERS)

    _clear(app)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NOT_CONFIGURED"


async def test_answers_409_not_configured_even_when_the_account_has_no_score(
    app: FastAPI, client: httpx.AsyncClient
) -> None:
    """As the [Outreach and CRM contracts](/architecture/interfaces.md#outreach-and-crm) `API-59`
    note states, the token check precedes the score lookup, so an unscored account (any random
    id, since no score exists in this app) still answers `409`, never `404`."""
    _override(app, _principal())

    response = await client.post(_crm_push_url(account_id=uuid.uuid4()), headers=_CSRF_HEADERS)

    _clear(app)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "NOT_CONFIGURED"


async def test_answers_404_not_found_when_the_account_has_no_score_for_the_service(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_push_to_crm(*args: object, **kwargs: object) -> CrmSyncResult:
        raise ScoreNotFound("No current score.")

    monkeypatch.setattr("leadradar.api.outreach_and_crm.push_to_crm", fake_push_to_crm)
    _override(app, _principal())

    response = await client.post(_crm_push_url(), headers=_CSRF_HEADERS)

    _clear(app)
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "NOT_FOUND"


async def test_answers_503_upstream_unavailable_with_hubspot_dependency_and_reason(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_push_to_crm(*args: object, **kwargs: object) -> CrmSyncResult:
        raise CrmUnavailable("HubSpot answered 401.")

    monkeypatch.setattr("leadradar.api.outreach_and_crm.push_to_crm", fake_push_to_crm)
    _override(app, _principal())

    response = await client.post(_crm_push_url(), headers=_CSRF_HEADERS)

    _clear(app)
    assert response.status_code == 503
    body = response.json()
    assert body["error"]["code"] == "UPSTREAM_UNAVAILABLE"
    assert body["error"]["details"]["dependency"] == "HUBSPOT"
    assert body["error"]["details"]["reason"] == "HubSpot answered 401."


@pytest.mark.parametrize(
    ("url", "field"),
    [
        (f"/api/v1/accounts/not-a-uuid/scores/{uuid.uuid4()}/crm-push", "id"),
        (f"/api/v1/accounts/{uuid.uuid4()}/scores/not-a-uuid/crm-push", "service_id"),
    ],
)
async def test_a_malformed_path_id_answers_422_validation_naming_the_parameter(
    app: FastAPI, client: httpx.AsyncClient, url: str, field: str
) -> None:
    _override(app, _principal())

    response = await client.post(url, headers=_CSRF_HEADERS)

    _clear(app)
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "VALIDATION"
    assert any(entry["field"] == field for entry in body["error"]["details"]["fields"])


async def test_answers_401_unauthenticated_without_the_session_cookie(
    client: httpx.AsyncClient,
) -> None:
    response = await client.post(_crm_push_url(), headers=_CSRF_HEADERS)

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "UNAUTHENTICATED"
    assert response.headers.get("x-request-id")


async def test_answers_403_forbidden_without_the_csrf_header(client: httpx.AsyncClient) -> None:
    response = await client.post(_crm_push_url())

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "FORBIDDEN"
    assert response.headers.get("x-request-id")


@pytest.mark.parametrize("role", [AppUserRole.SALES, AppUserRole.ADMIN])
async def test_admits_both_roles(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch, role: AppUserRole
) -> None:
    async def fake_push_to_crm(*args: object, **kwargs: object) -> CrmSyncResult:
        return _crm_sync_result()

    monkeypatch.setattr("leadradar.api.outreach_and_crm.push_to_crm", fake_push_to_crm)
    _override(app, _principal(role))

    response = await client.post(_crm_push_url(), headers=_CSRF_HEADERS)

    _clear(app)
    assert response.status_code == 200
