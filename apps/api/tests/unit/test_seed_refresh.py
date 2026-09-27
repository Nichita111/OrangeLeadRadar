"""The demo refresh succeeds only when all requested runs succeed."""

from __future__ import annotations

import uuid
from typing import cast
from unittest.mock import MagicMock

import pytest
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import PipelineRunStatus
from leadradar.seed import refresh
from leadradar.settings import ApiSettings

pytestmark = pytest.mark.unit


def _settings() -> ApiSettings:
    return ApiSettings(
        database_url=SecretStr("postgresql://u:p@localhost/db"),
        migration_database_url=SecretStr("postgresql://u:p@localhost/db"),
    )


@pytest.mark.parametrize(
    "status",
    [PipelineRunStatus.FAILED, PipelineRunStatus.PARTIAL, PipelineRunStatus.CANCELLED],
)
async def test_refresh_rejects_unsuccessful_terminal_runs(
    monkeypatch: pytest.MonkeyPatch, status: PipelineRunStatus
) -> None:
    run_id = uuid.uuid4()

    async def statuses(
        _db: AsyncSession, _ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, PipelineRunStatus]:
        return {run_id: status}

    monkeypatch.setattr(refresh, "_run_statuses", statuses)
    with pytest.raises(RuntimeError, match=status.value):
        await refresh.wait_for_runs_final(cast(AsyncSession, MagicMock()), [run_id], _settings())


async def test_refresh_rejects_a_missing_run(monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = uuid.uuid4()

    async def statuses(
        _db: AsyncSession, _ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, PipelineRunStatus]:
        return {}

    monkeypatch.setattr(refresh, "_run_statuses", statuses)
    with pytest.raises(LookupError, match=str(run_id)):
        await refresh.wait_for_runs_final(cast(AsyncSession, MagicMock()), [run_id], _settings())


async def test_refresh_accepts_successful_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    run_id = uuid.uuid4()

    async def statuses(
        _db: AsyncSession, _ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, PipelineRunStatus]:
        return {run_id: PipelineRunStatus.SUCCEEDED}

    monkeypatch.setattr(refresh, "_run_statuses", statuses)
    await refresh.wait_for_runs_final(cast(AsyncSession, MagicMock()), [run_id], _settings())
