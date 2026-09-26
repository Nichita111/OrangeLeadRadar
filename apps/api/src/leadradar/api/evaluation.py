"""Admin-only `API-77` Impact route of the
[Evaluation](/architecture/interfaces.md#evaluation-contracts) family."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.authentication import require_admin
from leadradar.db.models.identity import AppUser
from leadradar.db.session import get_session
from leadradar.evaluation.impact import read_impact

router = APIRouter(tags=["evaluation"])


class Impact(BaseModel):
    """[`Impact`](/architecture/interfaces.md#impact), the response of `API-77`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    period_days: int
    accounts_refreshed: int
    refreshes: int
    cost_per_refresh_eur: float | None
    minutes_per_refresh: float | None
    findings_created: int
    precision: float | None
    labelled_items: int | None
    manual_minutes_per_account: int
    manual_hours_replaced: float


@router.get("/impact")
async def get_impact(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    _admin: Annotated[AppUser, Depends(require_admin)],
) -> Impact:
    """`API-77`: computed on read by [Impact](/architecture/rules.md#impact); writes nothing."""
    settings = request.app.state.settings
    current_time = request.app.state.clock()
    report = await read_impact(session, settings, current_time)
    return Impact(
        period_days=report.period_days,
        accounts_refreshed=report.accounts_refreshed,
        refreshes=report.refreshes,
        cost_per_refresh_eur=report.cost_per_refresh_eur,
        minutes_per_refresh=report.minutes_per_refresh,
        findings_created=report.findings_created,
        precision=report.precision,
        labelled_items=report.labelled_items,
        manual_minutes_per_account=report.manual_minutes_per_account,
        manual_hours_replaced=report.manual_hours_replaced,
    )
