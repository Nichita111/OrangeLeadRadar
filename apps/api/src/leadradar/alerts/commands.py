"""[Alerts](/architecture/rules.md#alerts) (`S-PRO-06`), the api's half: acknowledging one for
the whole team (`API-49`), in the request's one transaction, the one authentication opened on the
session, committed here or rolled back on any error ([api Design]
(/architecture/services/api.md#design) Transactions)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.alerts.errors import AlertNotFound
from leadradar.alerts.queries import AlertRow, get_alert
from leadradar.db.models.identity import AppUser
from leadradar.db.models.signals import Alert


async def acknowledge_alert(
    session: AsyncSession, *, alert_id: uuid.UUID, principal: AppUser, now: datetime
) -> AlertRow:
    """`API-49`. Raises `AlertNotFound` when `alert_id` names no alert; acknowledging an already
    acknowledged alert leaves it unchanged (its first `acknowledged_by` and `acknowledged_at`
    stand)."""
    try:
        alert = (
            await session.execute(select(Alert).where(Alert.id == alert_id).with_for_update())
        ).scalar_one_or_none()
        if alert is None:
            raise AlertNotFound(f"No alert {alert_id}.")
        if alert.acknowledged_at is None:
            alert.acknowledged_by = principal.id
            alert.acknowledged_at = now
            await session.flush()
        result = await get_alert(session, alert_id)
    except BaseException:
        await session.rollback()
        raise
    await session.commit()
    return result
