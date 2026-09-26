"""Integration tests of requesting a quality check (`API-53`, D2) against a real database: only
one `EVALUATION` run may be queued or running at a time."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AppUserRole, AppUserStatus, PipelineRunKind, PipelineRunStatus
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import PipelineRun
from leadradar.evaluation.runs import request_quality_check

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


async def _admin(session: AsyncSession) -> AppUser:
    admin = AppUser(
        email="admin-eval@example.com",
        display_name="Admin",
        role=AppUserRole.ADMIN,
        status=AppUserStatus.ACTIVE,
        password_hash="hash",
        failed_logins=0,
        locked_until=None,
        last_login_at=None,
    )
    session.add(admin)
    await session.flush()
    return admin


class TestOneEvaluationAtATime:
    async def test_a_second_request_answers_the_run_already_queued(
        self, db_session: AsyncSession
    ) -> None:
        admin = await _admin(db_session)

        first = await request_quality_check(db_session, principal=admin, now=_NOW)
        second = await request_quality_check(db_session, principal=admin, now=_NOW)

        assert first.created is True
        assert second.created is False
        assert second.run.id == first.run.id

        rows = (
            (
                await db_session.execute(
                    select(PipelineRun).where(PipelineRun.kind == PipelineRunKind.EVALUATION)
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].status is PipelineRunStatus.QUEUED
