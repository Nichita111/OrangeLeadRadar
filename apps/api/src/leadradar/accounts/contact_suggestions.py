"""[Contact suggestion](/architecture/rules.md#contact-suggestion) (`API-94`, `S-ACC-07`): selects
the account's passages most likely to name its people, asks the LLM who they are through the AI
gateway (`API-95`) and keeps the grounded ones. Nothing is written here; the only row the call
leaves is the `AI_CALL` audit row the AI gateway writes in its own transaction
([ADR-29](/architecture/adrs/adr-29-contact-suggestions-added-by-a-person.md))."""

from __future__ import annotations

import uuid

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.accounts.errors import AccountNotFound
from leadradar.accounts.passages import retrieve_account_passages
from leadradar.ai.audit import AiCallContext
from leadradar.ai.gateway import AiGateway
from leadradar.ai.settings import AiGatewaySettings
from leadradar.ai.shapes import ContactExtractionInput, ContactExtractionPassage
from leadradar.core.contact_suggestion import (
    HINT_TERMS,
    QUESTION_TEXT,
    Candidate,
    Suggestion,
    SuggestionPassage,
    keep_suggestions,
)
from leadradar.db.models.accounts import Account, Contact


async def suggest_contacts(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    gateway: AiGateway,
    embedder: httpx.AsyncClient,
    settings: AiGatewaySettings,
    max_passages: int,
    max_suggestions: int,
    actor_id: uuid.UUID,
) -> list[Suggestion]:
    """`API-94`: at most `max_suggestions` (`CONTACT_SUGGESTION_MAX`) from the first
    `max_passages` (`CONTACT_SUGGESTION_MAX_PASSAGES`) passages; no passage, no LLM call.
    Raises `AccountNotFound`, and the embedder's and the AI gateway's errors."""
    account = await session.get(Account, account_id)
    if account is None:
        raise AccountNotFound(f"No account {account_id}.")
    passages = await retrieve_account_passages(
        session,
        account,
        text=QUESTION_TEXT,
        hint_terms=HINT_TERMS,
        source_types=None,
        settings=settings,
        embedder=embedder,
        limit=max_passages,
    )
    if not passages:
        return []
    existing_names = (
        await session.execute(select(Contact.full_name).where(Contact.account_id == account.id))
    ).scalars()
    candidates = await gateway.extract_contacts(
        ContactExtractionInput(
            account_name=account.name,
            passages=[
                ContactExtractionPassage(id=str(p.chunk_id), header=p.header, text=p.text)
                for p in passages
            ],
        ),
        AiCallContext(entity_type="account", entity_id=account.id, actor_id=actor_id),
    )
    return keep_suggestions(
        [
            Candidate(
                full_name=c.full_name,
                job_title=c.job_title,
                passage_id=c.passage_id,
                quote=c.quote,
            )
            for c in candidates
        ],
        [
            SuggestionPassage(
                id=str(p.chunk_id),
                text=p.text,
                source_url=p.url,
                document_title=p.title,
                published_at=p.published_at,
            )
            for p in passages
        ],
        existing_names=list(existing_names),
        limit=max_suggestions,
    )
