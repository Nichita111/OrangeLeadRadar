"""Router of the [Accounts and contacts](/architecture/interfaces.md#accounts-and-contacts)
family, its contacts half: `API-25` to `API-28` and `API-94`. The accounts half (`API-20` to
`API-24`) is built in `leadradar.api.accounts`; the capabilities are `leadradar.accounts.contacts`
and `leadradar.accounts.contact_suggestions`."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.accounts import contacts as contact_commands
from leadradar.accounts.contact_suggestions import suggest_contacts
from leadradar.accounts.contacts import ContactFields
from leadradar.api.authentication import CurrentUser
from leadradar.core.enums import ContactPersona, ContactPersonaOrigin
from leadradar.db.models.accounts import Contact as ContactModel
from leadradar.db.session import get_session

router = APIRouter(tags=["accounts-and-contacts"])


class Contact(BaseModel):
    """[`Contact`](/architecture/interfaces.md#contact)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    account_id: str
    full_name: str
    job_title: str
    source_url: str
    persona: ContactPersona
    persona_origin: ContactPersonaOrigin
    retain_until: str


class ContactCreate(BaseModel):
    """[`ContactCreate`](/architecture/interfaces.md#contactcreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    full_name: str
    job_title: str
    source_url: str
    persona: ContactPersona | SkipJsonSchema[None] = None


class ContactUpdate(BaseModel):
    """[`ContactUpdate`](/architecture/interfaces.md#contactupdate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    full_name: str | SkipJsonSchema[None] = None
    job_title: str | SkipJsonSchema[None] = None
    source_url: str | SkipJsonSchema[None] = None
    persona: ContactPersona | SkipJsonSchema[None] = None


class ContactSuggestion(BaseModel):
    """[`ContactSuggestion`](/architecture/interfaces.md#contactsuggestion)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    full_name: str
    job_title: str
    source_url: str
    quote: str
    document_title: str | None
    published_at: str | None


def _to_contact(contact: ContactModel) -> Contact:
    return Contact(
        id=str(contact.id),
        account_id=str(contact.account_id),
        full_name=contact.full_name,
        job_title=contact.job_title,
        source_url=contact.source_url,
        persona=contact.persona,
        persona_origin=contact.persona_origin,
        retain_until=contact.retain_until.isoformat(),
    )


@router.get("/accounts/{id}/contacts", response_model=list[Contact])
async def list_contacts(
    id: uuid.UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _principal: CurrentUser,
) -> list[Contact]:
    """`API-25`."""
    return [_to_contact(contact) for contact in await contact_commands.list_contacts(session, id)]


@router.post("/accounts/{id}/contacts", response_model=Contact)
async def create_contact(
    id: uuid.UUID,
    payload: ContactCreate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> Contact:
    """`API-26`."""
    settings = request.app.state.settings
    contact = await contact_commands.create_contact(
        session,
        account_id=id,
        full_name=payload.full_name,
        job_title=payload.job_title,
        source_url=payload.source_url,
        persona=payload.persona,
        gateway=request.app.state.ai_gateway,
        min_p=settings.attribute_min_p,
        retention_days=settings.contact_retention_days,
        actor_id=principal.id,
        now=request.app.state.clock(),
    )
    return _to_contact(contact)


@router.post("/accounts/{id}/contact-suggestions", response_model=list[ContactSuggestion])
async def list_contact_suggestions(
    id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> list[ContactSuggestion]:
    """`API-94`: computed on request and never stored."""
    state = request.app.state
    suggestions = await suggest_contacts(
        session,
        account_id=id,
        gateway=state.ai_gateway,
        embedder=state.embedder_client,
        settings=state.settings,
        max_passages=state.settings.contact_suggestion_max_passages,
        max_suggestions=state.settings.contact_suggestion_max,
        actor_id=principal.id,
    )
    return [
        ContactSuggestion(
            full_name=suggestion.full_name,
            job_title=suggestion.job_title,
            source_url=suggestion.source_url,
            quote=suggestion.quote,
            document_title=suggestion.document_title,
            published_at=(
                None if suggestion.published_at is None else suggestion.published_at.isoformat()
            ),
        )
        for suggestion in suggestions
    ]


@router.patch("/contacts/{id}", response_model=Contact)
async def update_contact(
    id: uuid.UUID,
    payload: ContactUpdate,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> Contact:
    """`API-27`."""
    contact = await contact_commands.update_contact(
        session,
        contact_id=id,
        fields=ContactFields(
            full_name=payload.full_name,
            job_title=payload.job_title,
            source_url=payload.source_url,
            persona=payload.persona,
        ),
        gateway=request.app.state.ai_gateway,
        min_p=request.app.state.settings.attribute_min_p,
        actor_id=principal.id,
        now=request.app.state.clock(),
    )
    return _to_contact(contact)


@router.delete("/contacts/{id}", status_code=204)
async def delete_contact(
    id: uuid.UUID,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> None:
    """`API-28`."""
    await contact_commands.erase_contact(
        session, contact_id=id, actor_id=principal.id, now=request.app.state.clock()
    )
