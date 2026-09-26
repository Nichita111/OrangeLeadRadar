"""Contract tests for `API-18` (activate a DRAFT scoring config).

Coverage: `API-18`, `AC-06` (activation creates ACTIVE config + 409 on wrong state).
"""

from __future__ import annotations

import uuid
from datetime import UTC
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from leadradar.scoring.activate import ActivationResult
from leadradar.scoring.errors import NotADraft, ScoringConfigNotFound

pytestmark = pytest.mark.contract

_CSRF_HEADERS = {"X-Requested-With": "XMLHttpRequest"}


def _make_activation_result(
    status: str = "ACTIVE",
) -> ActivationResult:
    from datetime import datetime

    from leadradar.core.enums import ScoringConfigStatus

    status_enum = ScoringConfigStatus(status)
    return ActivationResult(
        id=uuid.uuid4(),
        service_id=uuid.uuid4(),
        version=2,
        status=status_enum,
        change_note="test note",
        activated_at=datetime(2026, 9, 25, 6, 0, 0, tzinfo=UTC),
        activated_by=uuid.uuid4(),
        run_id=uuid.uuid4(),
        settings={"fit_weight": 0.4, "intent_weight": 0.6},
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


async def test_api18_draft_returns_scoring_config_active(
    admin_client: httpx.AsyncClient,
) -> None:
    """API-18 on a DRAFT returns 200 with ScoringConfig status=ACTIVE (AC-06)."""
    config_id = uuid.uuid4()
    result = _make_activation_result("ACTIVE")

    with patch(
        "leadradar.api.scoring.activate_scoring_config",
        new=AsyncMock(return_value=result),
    ):
        response = await admin_client.post(
            f"/api/v1/scoring-configs/{config_id}/activate",
            json={"change_note": "promoting to prod"},
        )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACTIVE"
    assert body["version"] == 2
    assert body["change_note"] == "test note"
    assert "id" in body
    assert "service_id" in body
    assert "settings" in body
    assert "activated_at" in body


# ---------------------------------------------------------------------------
# Error cases — wrong state
# ---------------------------------------------------------------------------


async def test_api18_active_config_returns_409(
    admin_client: httpx.AsyncClient,
) -> None:
    """API-18 on an ACTIVE config returns 409 CONFLICT (API-18, AC-06)."""
    config_id = uuid.uuid4()

    with patch(
        "leadradar.api.scoring.activate_scoring_config",
        new=AsyncMock(side_effect=NotADraft(str(config_id), "ACTIVE")),
    ):
        response = await admin_client.post(
            f"/api/v1/scoring-configs/{config_id}/activate",
            json={"change_note": "promoting"},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "CONFLICT"


async def test_api18_retired_config_returns_409(
    admin_client: httpx.AsyncClient,
) -> None:
    """API-18 on a RETIRED config returns 409 CONFLICT (API-18, AC-06)."""
    config_id = uuid.uuid4()

    with patch(
        "leadradar.api.scoring.activate_scoring_config",
        new=AsyncMock(side_effect=NotADraft(str(config_id), "RETIRED")),
    ):
        response = await admin_client.post(
            f"/api/v1/scoring-configs/{config_id}/activate",
            json={"change_note": "promoting"},
        )

    assert response.status_code == 409
    body = response.json()
    assert body["error"]["code"] == "CONFLICT"
    assert "RETIRED" in body["error"]["message"]


async def test_api18_not_found_returns_404(
    admin_client: httpx.AsyncClient,
) -> None:
    """API-18 with an unknown config_id returns 404 NOT_FOUND."""
    config_id = uuid.uuid4()

    with patch(
        "leadradar.api.scoring.activate_scoring_config",
        new=AsyncMock(side_effect=ScoringConfigNotFound(str(config_id))),
    ):
        response = await admin_client.post(
            f"/api/v1/scoring-configs/{config_id}/activate",
            json={"change_note": "promoting"},
        )

    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "NOT_FOUND"


# ---------------------------------------------------------------------------
# Auth / role enforcement
# ---------------------------------------------------------------------------


async def test_api18_sales_role_returns_403(
    sales_client: httpx.AsyncClient,
) -> None:
    """API-18 with Sales role returns 403 FORBIDDEN (Conventions)."""
    config_id = uuid.uuid4()

    response = await sales_client.post(
        f"/api/v1/scoring-configs/{config_id}/activate",
        json={"change_note": "promoting"},
    )

    assert response.status_code == 403
    body = response.json()
    assert body["error"]["code"] == "FORBIDDEN"


async def test_api18_no_session_returns_401(
    client: httpx.AsyncClient,
) -> None:
    """API-18 with no session returns 401 UNAUTHENTICATED (Conventions)."""
    config_id = uuid.uuid4()

    response = await client.post(
        f"/api/v1/scoring-configs/{config_id}/activate",
        json={"change_note": "promoting"},
        headers=_CSRF_HEADERS,
    )

    assert response.status_code == 401
    body = response.json()
    assert body["error"]["code"] == "UNAUTHENTICATED"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


async def test_api18_missing_change_note_returns_422(
    admin_client: httpx.AsyncClient,
) -> None:
    """API-18 without change_note in the body returns 422 (API-18 shape)."""
    config_id = uuid.uuid4()

    response = await admin_client.post(
        f"/api/v1/scoring-configs/{config_id}/activate",
        json={},
    )

    assert response.status_code == 422
