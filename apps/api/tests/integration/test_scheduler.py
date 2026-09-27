"""Integration tests of the worker scheduler's tick against a real database
([Scheduler and housekeeping](/architecture/services/worker.md#scheduler-and-housekeeping) as
amended, G3): the advisory lock, and the housekeeping wired into the tick."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import Connection, func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, AsyncSession

from leadradar.db.models.accounts import Contact
from leadradar.worker.scheduler import (
    _SCHEDULER_LOCK_KEY,
    HousekeepingTracker,
    run_scheduler_tick,
)
from tests.integration import factories as f

pytestmark = pytest.mark.integration

NOW = datetime(2026, 9, 27, 4, 0, tzinfo=UTC)
PAST_DAY = date(2026, 9, 26)


def _session_factory(connection: AsyncConnection) -> Callable[[], AsyncSession]:
    def make() -> AsyncSession:
        return AsyncSession(
            bind=connection, join_transaction_mode="create_savepoint", expire_on_commit=False
        )

    return make


async def _tick(connection: AsyncConnection, tracker: HousekeepingTracker, *, now: datetime) -> int:
    return await run_scheduler_tick(
        _session_factory(connection),
        clock=lambda: now,
        max_enqueue=20,
        keys_configured=frozenset(),
        housekeeping_hour_utc=3,
        session_ttl_hours=12,
        housekeeping=tracker,
    )


async def test_two_ticks_the_same_day_after_the_hour_run_the_housekeeping_once(
    async_connection: AsyncConnection,
) -> None:
    tracker = HousekeepingTracker()

    with patch(
        "leadradar.worker.scheduler.run_housekeeping", new_callable=AsyncMock
    ) as housekeeping:
        await _tick(async_connection, tracker, now=NOW)
        await _tick(async_connection, tracker, now=NOW + timedelta(minutes=1))

    assert housekeeping.await_count == 1
    assert tracker.last_day == NOW.date()


async def test_a_tick_before_the_hour_does_not_run_the_housekeeping(
    async_connection: AsyncConnection,
) -> None:
    tracker = HousekeepingTracker()

    with patch(
        "leadradar.worker.scheduler.run_housekeeping", new_callable=AsyncMock
    ) as housekeeping:
        await _tick(async_connection, tracker, now=NOW.replace(hour=2))

    assert housekeeping.await_count == 0
    assert tracker.last_day is None


async def test_a_tick_while_the_lock_is_held_runs_neither_refresh_nor_housekeeping(
    async_connection: AsyncConnection, async_engine: AsyncEngine
) -> None:
    def build(conn: Connection) -> object:
        account_id = f.make_account(conn, next_refresh_at=NOW - timedelta(hours=1))
        return f.make_contact(conn, account_id, retain_until=PAST_DAY)

    contact_id = await async_connection.run_sync(build)
    tracker = HousekeepingTracker()

    async with async_engine.connect() as holder, holder.begin():
        await holder.execute(select(func.pg_advisory_xact_lock(_SCHEDULER_LOCK_KEY)))

        with patch(
            "leadradar.worker.scheduler.run_housekeeping", new_callable=AsyncMock
        ) as housekeeping:
            selected = await _tick(async_connection, tracker, now=NOW)

    assert selected == 0
    assert housekeeping.await_count == 0
    assert tracker.last_day is None
    async with AsyncSession(async_connection, expire_on_commit=False) as session:
        assert await session.get(Contact, contact_id) is not None


async def test_after_a_tick_that_fails_past_housekeeping_the_next_tick_reruns_it(
    async_connection: AsyncConnection,
) -> None:
    """R-5: the failing tick's housekeeping rolls back with the rest of its transaction, so
    `housekeeping.last_day` must not be recorded until the transaction has committed — a later
    tick the same day must rerun the housekeeping, not skip it as already done."""
    tracker = HousekeepingTracker()

    with (
        patch(
            "leadradar.worker.scheduler.run_housekeeping", new_callable=AsyncMock
        ) as first_housekeeping,
        patch(
            "leadradar.worker.scheduler.due_refresh_account_ids",
            side_effect=RuntimeError("boom after housekeeping"),
        ),
        pytest.raises(RuntimeError, match="boom after housekeeping"),
    ):
        await _tick(async_connection, tracker, now=NOW)

    assert first_housekeeping.await_count == 1
    assert tracker.last_day is None

    with patch(
        "leadradar.worker.scheduler.run_housekeeping", new_callable=AsyncMock
    ) as retried_housekeeping:
        await _tick(async_connection, tracker, now=NOW + timedelta(minutes=1))

    assert retried_housekeeping.await_count == 1
    assert tracker.last_day == NOW.date()
