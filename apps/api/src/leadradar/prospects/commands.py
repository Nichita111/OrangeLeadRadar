"""Writes of the [Prospects and evidence](/architecture/interfaces.md#prospects-and-evidence)
family: `API-44` creates a disqualifier override and `API-45` revokes one. Each appends its audit
row and enqueues a `RESCORE` with trigger `OVERRIDE` in one transaction, and answers the
[`Override`](/architecture/interfaces.md#override) with that run's id."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.core.enums import AuditAction, DisqualifierOverrideStatus, PipelineRunTrigger
from leadradar.db.models.identity import AppUser
from leadradar.db.models.signals import AccountScore, DisqualifierOverride
from leadradar.prospects.errors import OverrideConflict, OverrideRuleInvalid, ProspectNotFound
from leadradar.prospects.queries import active_disqualifier_labels, override_views
from leadradar.runs.enqueue import enqueue_account_rescore


async def _currently_matches(
    session: AsyncSession, account_id: uuid.UUID, service_id: uuid.UUID, rule_key: str
) -> bool:
    breakdown = (
        await session.execute(
            select(AccountScore.breakdown).where(
                AccountScore.account_id == account_id,
                AccountScore.service_id == service_id,
                AccountScore.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    entries = breakdown.get("disqualifiers") if isinstance(breakdown, dict) else None
    return any(
        isinstance(entry, dict) and entry.get("key") == rule_key and entry.get("matched")
        for entry in (entries if isinstance(entries, list) else [])
    )


async def create_override(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
    rule_key: str,
    note: str,
    principal: AppUser,
    now: datetime,
) -> dict[str, object]:
    """`API-44`. Raises `OverrideRuleInvalid` when `rule_key` names no rule of the active
    settings that currently matches, `OverrideConflict` when it already has an active override."""
    try:
        labels = await active_disqualifier_labels(session, service_id)
        if rule_key not in labels or not await _currently_matches(
            session, account_id, service_id, rule_key
        ):
            raise OverrideRuleInvalid(
                "The rule is not one of the active settings that matches this account."
            )
        existing = (
            await session.execute(
                select(DisqualifierOverride.id).where(
                    DisqualifierOverride.account_id == account_id,
                    DisqualifierOverride.service_id == service_id,
                    DisqualifierOverride.rule_key == rule_key,
                    DisqualifierOverride.status == DisqualifierOverrideStatus.ACTIVE,
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise OverrideConflict("The rule already has an active override.", entity_id=existing)

        override = DisqualifierOverride(
            account_id=account_id,
            service_id=service_id,
            rule_key=rule_key,
            note=note,
            created_by=principal.id,
            status=DisqualifierOverrideStatus.ACTIVE,
            revoked_by=None,
            revoked_at=None,
        )
        session.add(override)
        await session.flush()
        await append_audit_event(
            session,
            action=AuditAction.OVERRIDE_CREATED,
            occurred_at=now,
            actor_id=principal.id,
            entity_type="disqualifier_override",
            entity_id=override.id,
            payload={"rule_key": rule_key},
        )
        run_id = await enqueue_account_rescore(
            session,
            account_id=account_id,
            service_id=service_id,
            trigger=PipelineRunTrigger.OVERRIDE,
            requested_by=principal.id,
            now=now,
        )
        await session.refresh(override)
        [view] = await override_views(session, [override], run_id=run_id)
    except BaseException:
        await session.rollback()
        raise
    await session.commit()
    return view


async def revoke_override(
    session: AsyncSession, *, override_id: uuid.UUID, principal: AppUser, now: datetime
) -> dict[str, object]:
    """`API-45`. Raises `ProspectNotFound` for an unknown override and `OverrideConflict` for
    one already revoked."""
    try:
        override = (
            await session.execute(
                select(DisqualifierOverride)
                .where(DisqualifierOverride.id == override_id)
                .with_for_update()
            )
        ).scalar_one_or_none()
        if override is None:
            raise ProspectNotFound("The override does not exist.")
        if override.status is not DisqualifierOverrideStatus.ACTIVE:
            raise OverrideConflict("The override is already revoked.", entity_id=override.id)
        override.status = DisqualifierOverrideStatus.REVOKED
        override.revoked_by = principal.id
        override.revoked_at = now
        await session.flush()
        await append_audit_event(
            session,
            action=AuditAction.OVERRIDE_REVOKED,
            occurred_at=now,
            actor_id=principal.id,
            entity_type="disqualifier_override",
            entity_id=override.id,
            payload={"rule_key": override.rule_key},
        )
        run_id = await enqueue_account_rescore(
            session,
            account_id=override.account_id,
            service_id=override.service_id,
            trigger=PipelineRunTrigger.OVERRIDE,
            requested_by=principal.id,
            now=now,
        )
        await session.refresh(override)
        [view] = await override_views(session, [override], run_id=run_id)
    except BaseException:
        await session.rollback()
        raise
    await session.commit()
    return view
