"""Integration tests of `accounts.contact_suggestions.suggest_contacts` (`API-91`, `S-ACC-06`)
against a real database: [Contact suggestion](/architecture/rules.md#contact-suggestion) reads
the account's stored passages and writes nothing. The AI gateway is a fake that records its input;
the embedder answers over an `httpx.MockTransport`."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

import httpx
import pytest
from sqlalchemy import Connection, func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncSession

from leadradar.accounts.contact_suggestions import suggest_contacts
from leadradar.accounts.errors import AccountNotFound
from leadradar.ai.audit import AiCallContext
from leadradar.ai.shapes import ContactCandidate, ContactExtractionInput
from leadradar.core.enums import DocumentSourceType
from leadradar.db.models.accounts import Contact
from leadradar.settings import ApiSettings
from tests.integration import factories as f

pytestmark = pytest.mark.integration

_BOARD_TEXT = (
    "Board of Management. Dr. Tobias Meyer, Chief Executive Officer. Melanie Kreis, Chief "
    "Financial Officer. Press contact: presse@example.com, +49 228 182-9944."
)


class _Gateway:
    def __init__(self, answer: list[ContactCandidate]) -> None:
        self.answer = answer
        self.inputs: list[ContactExtractionInput] = []

    async def extract_contacts(
        self, role_input: ContactExtractionInput, context: AiCallContext
    ) -> list[ContactCandidate]:
        self.inputs.append(role_input)
        return self.answer


def _embedder(dim: int) -> httpx.AsyncClient:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=[[0.1] * dim])

    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def _unit_vector(dim: int) -> list[float]:
    return [1.0] + [0.0] * (dim - 1)


async def _account_with_board_page(
    connection: AsyncConnection, *, dim: int
) -> tuple[uuid.UUID, uuid.UUID]:
    def insert(conn: Connection) -> tuple[uuid.UUID, uuid.UUID]:
        account_id = f.make_account(conn, domain="board.example.com", name="Board Group")
        run_id = f.make_pipeline_run(conn)
        document_id = f.make_document(
            conn,
            run_id,
            account_id=account_id,
            source_type=DocumentSourceType.COMPANY_PUBLICATION,
            url="https://board.example.com/board",
            title="Board of Management",
            published_at=datetime(2026, 8, 5, tzinfo=UTC),
            text=_BOARD_TEXT,
        )
        chunk_id = f.make_chunk(
            conn,
            document_id,
            char_end=len(_BOARD_TEXT),
            text=_BOARD_TEXT,
            embedding=_unit_vector(dim),
        )
        return account_id, chunk_id

    return await connection.run_sync(insert)


async def _suggest(
    session: AsyncSession, settings: ApiSettings, account_id: uuid.UUID, gateway: _Gateway
) -> Any:
    return await suggest_contacts(
        session,
        account_id=account_id,
        gateway=gateway,  # type: ignore[arg-type]
        embedder=_embedder(settings.embedding_dim),
        settings=settings,
        max_passages=settings.contact_suggestion_max_passages,
        max_suggestions=settings.contact_suggestion_max,
        actor_id=uuid.uuid4(),
    )


async def test_the_account_s_passage_is_asked_and_grounded_people_are_suggested_unstored(
    async_connection: AsyncConnection, async_session: AsyncSession, api_settings: ApiSettings
) -> None:
    account_id, chunk_id = await _account_with_board_page(
        async_connection, dim=api_settings.embedding_dim
    )
    await async_connection.run_sync(
        lambda conn: f.make_contact(conn, account_id, full_name="Melanie Kreis")
    )
    passage_id = str(chunk_id)
    gateway = _Gateway(
        [
            ContactCandidate(
                full_name="Dr. Tobias Meyer",
                job_title="Chief Executive Officer",
                passage_id=passage_id,
                quote="Dr. Tobias Meyer, Chief Executive Officer.",
            ),
            ContactCandidate(
                full_name="Melanie Kreis",
                job_title="Chief Financial Officer",
                passage_id=passage_id,
                quote="Melanie Kreis, Chief Financial Officer.",
            ),
            ContactCandidate(
                full_name="presse@example.com",
                job_title="Press contact",
                passage_id=passage_id,
                quote="Press contact: presse@example.com",
            ),
        ]
    )

    suggestions = await _suggest(async_session, api_settings, account_id, gateway)

    [role_input] = gateway.inputs
    assert role_input.account_name == "Board Group"
    assert [(p.id, p.text) for p in role_input.passages] == [(passage_id, _BOARD_TEXT)]
    assert role_input.passages[0].header == "Board Group · Board of Management · 2026-08-05"
    assert [(s.full_name, s.job_title, s.source_url) for s in suggestions] == [
        ("Dr. Tobias Meyer", "Chief Executive Officer", "https://board.example.com/board")
    ]
    contacts = await async_session.execute(
        select(func.count()).select_from(Contact).where(Contact.account_id == account_id)
    )
    assert contacts.scalar_one() == 1


async def test_an_account_without_stored_passages_gets_no_suggestion_and_no_llm_call(
    async_connection: AsyncConnection, async_session: AsyncSession, api_settings: ApiSettings
) -> None:
    account_id = await async_connection.run_sync(
        lambda conn: f.make_account(conn, domain="quiet.example.com", name="Quiet AG")
    )
    gateway = _Gateway([])

    assert await _suggest(async_session, api_settings, account_id, gateway) == []
    assert gateway.inputs == []


async def test_an_unknown_account_is_not_found(
    async_session: AsyncSession, api_settings: ApiSettings
) -> None:
    with pytest.raises(AccountNotFound):
        await _suggest(async_session, api_settings, uuid.uuid4(), _Gateway([]))
