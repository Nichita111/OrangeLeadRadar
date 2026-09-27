"""Integration tests of `make export-labels` and `make seed-labels`
([Seeding](/architecture/overview.md#runtime) after D6, `S-RUN-03`) against a real database, per
"Tests for the coder" of `.work/labelling-and-quality/design.md`."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import AppUserRole, AppUserStatus, EvaluationItemStatus, FindingStrength
from leadradar.db.models.feedback import EvaluationItem
from leadradar.db.models.identity import AppUser
from leadradar.seed.demo import DEMO_ADMIN_EMAIL
from leadradar.seed.labels import LabelEntriesUnmatched, LabelEntry, export_entries, load_entries
from tests.integration import factories

pytestmark = pytest.mark.integration

_NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


async def _seed(session: AsyncSession, make: Callable[..., Any], *a: Any, **kw: Any) -> Any:
    return await session.run_sync(lambda s: make(s.connection(), *a, **kw))


async def _demo_admin(session: AsyncSession) -> AppUser:
    admin = AppUser(
        email=DEMO_ADMIN_EMAIL,
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


async def _arrangement(session: AsyncSession, *, service_code: str) -> dict[str, Any]:
    account_domain = f"{uuid.uuid4().hex}.example.com"
    service_id = await _seed(session, factories.make_service, code=service_code)
    question_id = await _seed(
        session, factories.make_signal_question, service_id, key="COST_PROGRAM"
    )
    account_id = await _seed(session, factories.make_account, domain=account_domain)
    run_id = await _seed(session, factories.make_pipeline_run)
    content_hash = uuid.uuid4().hex
    document_id = await _seed(
        session, factories.make_document, run_id, account_id=account_id, content_hash=content_hash
    )
    chunk_id = await _seed(session, factories.make_chunk, document_id, ordinal=0)
    return {
        "service_id": service_id,
        "service_code": service_code,
        "question_id": question_id,
        "chunk_id": chunk_id,
        "account_domain": account_domain,
        "content_hash": content_hash,
    }


class TestExportThenSeed:
    async def test_restores_every_label_onto_its_passage(self, db_session: AsyncSession) -> None:
        ids = await _arrangement(db_session, service_code="INTELLIGENT_AUTOMATION")
        admin = await _demo_admin(db_session)
        user_id = await _seed(db_session, factories.make_app_user)
        await _seed(
            db_session,
            factories.make_evaluation_item,
            ids["chunk_id"],
            ids["question_id"],
            user_id,
            expected_strength=FindingStrength.STRONG,
        )

        entries = await export_entries(db_session)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.account_domain == ids["account_domain"]
        assert entry.content_hash == ids["content_hash"]
        assert entry.service_code == "INTELLIGENT_AUTOMATION"
        assert entry.question_key == "COST_PROGRAM"
        assert entry.expected_strength == "STRONG"

        # A fresh load, as `make seed-labels` would run on a re-refreshed dataset, restores it.
        await load_entries(db_session, entries, now=_NOW)

        item = (
            await db_session.execute(
                select(EvaluationItem).where(
                    EvaluationItem.chunk_id == ids["chunk_id"],
                    EvaluationItem.question_id == ids["question_id"],
                    EvaluationItem.status == EvaluationItemStatus.ACTIVE,
                )
            )
        ).scalar_one()
        assert item.expected_strength == FindingStrength.STRONG
        assert item.labelled_by == admin.id

    async def test_export_distinguishes_the_same_question_key_in_two_services(
        self, db_session: AsyncSession
    ) -> None:
        first = await _arrangement(db_session, service_code="SERVICE_ONE")
        second = await _arrangement(db_session, service_code="SERVICE_TWO")
        user_id = await _seed(db_session, factories.make_app_user)
        await _seed(
            db_session,
            factories.make_evaluation_item,
            first["chunk_id"],
            first["question_id"],
            user_id,
            expected_strength=FindingStrength.WEAK,
        )
        await _seed(
            db_session,
            factories.make_evaluation_item,
            second["chunk_id"],
            second["question_id"],
            user_id,
            expected_strength=FindingStrength.STRONG,
        )

        entries = await export_entries(db_session)

        assert len(entries) == 2
        by_service = {entry.service_code: entry for entry in entries}
        assert by_service["SERVICE_ONE"].question_key == "COST_PROGRAM"
        assert by_service["SERVICE_TWO"].question_key == "COST_PROGRAM"
        assert by_service["SERVICE_ONE"].expected_strength == "WEAK"
        assert by_service["SERVICE_TWO"].expected_strength == "STRONG"


class TestSeedLabelsFailure:
    async def test_fails_listing_unmatched_entries_without_writing_the_matched_ones(
        self, db_session: AsyncSession
    ) -> None:
        ids = await _arrangement(db_session, service_code="INTELLIGENT_AUTOMATION")
        await _demo_admin(db_session)
        matched = LabelEntry(
            account_domain=ids["account_domain"],
            content_hash=ids["content_hash"],
            ordinal=0,
            service_code=ids["service_code"],
            question_key="COST_PROGRAM",
            question_revision=1,
            expected_strength="STRONG",
        )
        unmatched = LabelEntry(
            account_domain="no-such-domain.example.com",
            content_hash="no-such-hash",
            ordinal=0,
            service_code=ids["service_code"],
            question_key="COST_PROGRAM",
            question_revision=1,
            expected_strength="WEAK",
        )

        with pytest.raises(LabelEntriesUnmatched) as excinfo:
            await load_entries(db_session, [matched, unmatched], now=_NOW)
        assert len(excinfo.value.unmatched) == 1
        assert "no-such-domain.example.com" in excinfo.value.unmatched[0]

        rows = (
            (
                await db_session.execute(
                    select(EvaluationItem).where(EvaluationItem.chunk_id == ids["chunk_id"])
                )
            )
            .scalars()
            .all()
        )
        assert rows == []


class TestSeedLabelsIdempotent:
    async def test_a_second_load_rewrites_the_same_values(self, db_session: AsyncSession) -> None:
        ids = await _arrangement(db_session, service_code="INTELLIGENT_AUTOMATION")
        await _demo_admin(db_session)
        entry = LabelEntry(
            account_domain=ids["account_domain"],
            content_hash=ids["content_hash"],
            ordinal=0,
            service_code=ids["service_code"],
            question_key="COST_PROGRAM",
            question_revision=1,
            expected_strength="MEDIUM",
        )

        await load_entries(db_session, [entry], now=_NOW)
        await load_entries(db_session, [entry], now=_NOW)

        rows = (
            (
                await db_session.execute(
                    select(EvaluationItem).where(
                        EvaluationItem.chunk_id == ids["chunk_id"],
                        EvaluationItem.status == EvaluationItemStatus.ACTIVE,
                    )
                )
            )
            .scalars()
            .all()
        )
        assert len(rows) == 1
        assert rows[0].expected_strength == FindingStrength.MEDIUM
