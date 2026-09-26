"""Contract tests of `API-77` `GET /api/v1/impact`
([Evaluation contracts](/architecture/interfaces.md#evaluation-contracts)).

`API-77` ships with no role dependency yet (the recorded deviation of
`.work/impact-panel/design.md`), so no `403`/`401` role test is written here; issue #11 adds it
beside the guard it exercises."""

from __future__ import annotations

import httpx
import pytest
from fastapi import FastAPI

from leadradar.core.impact import ImpactReport
from leadradar.db.session import get_session

pytestmark = pytest.mark.contract

_REPORT = ImpactReport(
    period_days=30,
    accounts_refreshed=3,
    refreshes=4,
    cost_per_refresh_eur=1.25,
    minutes_per_refresh=6.5,
    findings_created=7,
    precision=0.91,
    labelled_items=250,
    manual_minutes_per_account=120,
    manual_hours_replaced=6.0,
)


async def test_impact_answers_200_with_exactly_the_shape_of_impact(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_read_impact(*args: object, **kwargs: object) -> ImpactReport:
        return _REPORT

    monkeypatch.setattr("leadradar.api.evaluation.read_impact", fake_read_impact)
    app.dependency_overrides[get_session] = lambda: None

    response = await client.get("/api/v1/impact")

    app.dependency_overrides.pop(get_session, None)
    assert response.status_code == 200
    body = response.json()
    assert set(body.keys()) == {
        "period_days",
        "accounts_refreshed",
        "refreshes",
        "cost_per_refresh_eur",
        "minutes_per_refresh",
        "findings_created",
        "precision",
        "labelled_items",
        "manual_minutes_per_account",
        "manual_hours_replaced",
    }
    assert isinstance(body["period_days"], int)
    assert isinstance(body["accounts_refreshed"], int)
    assert isinstance(body["refreshes"], int)
    assert isinstance(body["cost_per_refresh_eur"], float)
    assert isinstance(body["minutes_per_refresh"], float)
    assert isinstance(body["findings_created"], int)
    assert isinstance(body["precision"], float)
    assert isinstance(body["labelled_items"], int)
    assert isinstance(body["manual_minutes_per_account"], int)
    assert isinstance(body["manual_hours_replaced"], float)


async def test_impact_reports_null_cost_precision_and_labelled_items_without_runs_or_a_pass(
    app: FastAPI, client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    empty_report = ImpactReport(
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

    async def fake_read_impact(*args: object, **kwargs: object) -> ImpactReport:
        return empty_report

    monkeypatch.setattr("leadradar.api.evaluation.read_impact", fake_read_impact)
    app.dependency_overrides[get_session] = lambda: None

    response = await client.get("/api/v1/impact")

    app.dependency_overrides.pop(get_session, None)
    assert response.status_code == 200
    body = response.json()
    assert body["cost_per_refresh_eur"] is None
    assert body["minutes_per_refresh"] is None
    assert body["precision"] is None
    assert body["labelled_items"] is None
