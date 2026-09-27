"""[Accounts and contacts](/architecture/interfaces.md#accounts-and-contacts), the contacts half
(`API-25` to `API-28`, `S-ACC-04`): lists, creates, updates and erases
[`contact`](/architecture/sql-store.md#contact) rows, mapping the persona by
[Persona mapping](/architecture/rules.md#persona-mapping) through the AI gateway unless the user
gives one. The classifier is called before anything is written, so a `503` or `429` stores
nothing. Each function owns its own transaction, as [`commands`](commands.py) does."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.accounts.errors import AccountNotFound, ContactNotFound, ContactValidationError
from leadradar.ai.audit import AiCallContext
from leadradar.ai.gateway import AiGateway
from leadradar.ai.shapes import ClassifierOption, ClassifierQuestion, ClassifierRequest
from leadradar.audit.events import append_audit_event
from leadradar.core.enums import (
    AuditAction,
    ContactPersona,
    ContactPersonaOrigin,
    SignalQuestionAnswerType,
)
from leadradar.db.models.accounts import Account, Contact

#: [Persona mapping](/architecture/rules.md#persona-mapping): the exact question text; the
#: options are the [persona values](/architecture/sql-store.md#contact) labelled with their
#: meaning.
PERSONA_QUESTION_ID = "persona"
PERSONA_QUESTION_TEXT = "Which role best describes this job title?"
_PERSONA_LABELS: dict[ContactPersona, str] = {
    ContactPersona.CIO: "Chief information officer",
    ContactPersona.CTO: "Chief technology officer",
    ContactPersona.COO: "Chief operating officer",
    ContactPersona.CFO: "Chief financial officer",
    ContactPersona.CISO: "Chief information security officer",
    ContactPersona.HEAD_OF_DIGITAL_TRANSFORMATION: "Leads digital transformation",
    ContactPersona.HEAD_OF_AUTOMATION: "Leads automation, RPA or intelligent automation",
    ContactPersona.HEAD_OF_PROCESS_EXCELLENCE: (
        "Leads process excellence, lean or business process management"
    ),
    ContactPersona.HEAD_OF_SHARED_SERVICES: (
        "Leads a shared service centre or global business services"
    ),
    ContactPersona.OTHER: "Any other role",
}


@dataclass(frozen=True)
class ContactFields:
    """The text fields of [`ContactCreate`](/architecture/interfaces.md#contactcreate) and
    [`ContactUpdate`](/architecture/interfaces.md#contactupdate); `None` was not sent."""

    full_name: str | None = None
    job_title: str | None = None
    source_url: str | None = None
    persona: ContactPersona | None = None


def persona_request(job_title: str) -> ClassifierRequest:
    """The one-question [`ClassifierRequest`](/architecture/interfaces.md#classifierrequest) of
    [Persona mapping](/architecture/rules.md#persona-mapping) over a job title."""
    return ClassifierRequest(
        state=job_title,
        context=None,
        questions=[
            ClassifierQuestion(
                id=PERSONA_QUESTION_ID,
                kind=SignalQuestionAnswerType.CHOICE,
                text=PERSONA_QUESTION_TEXT,
                options=[
                    ClassifierOption(key=persona.value, label=label)
                    for persona, label in _PERSONA_LABELS.items()
                ],
            )
        ],
    )


def persona_from_probabilities(probabilities: dict[str, float], min_p: float) -> ContactPersona:
    """[Persona mapping](/architecture/rules.md#persona-mapping): the most probable persona when
    its probability is at least `min_p` (`ATTRIBUTE_MIN_P`), else `OTHER`."""
    if not probabilities:
        return ContactPersona.OTHER
    key, probability = max(probabilities.items(), key=lambda item: item[1])
    if probability < min_p:
        return ContactPersona.OTHER
    return ContactPersona(key)


async def _map_persona(
    gateway: AiGateway,
    job_title: str,
    *,
    min_p: float,
    account_id: uuid.UUID,
    actor_id: uuid.UUID,
) -> ContactPersona:
    answers = await gateway.classify(
        persona_request(job_title),
        AiCallContext(entity_type="account", entity_id=account_id, actor_id=actor_id),
    )
    probabilities = answers[0].probabilities if answers else {}
    return persona_from_probabilities(probabilities, min_p)


def _require_text(field: str, value: str | None) -> None:
    if value is not None and not value.strip():
        raise ContactValidationError(field, f"{field} must not be blank.")


async def _ensure_account(session: AsyncSession, account_id: uuid.UUID) -> None:
    found = (
        await session.execute(select(Account.id).where(Account.id == account_id))
    ).scalar_one_or_none()
    if found is None:
        raise AccountNotFound(f"No account {account_id}.")


async def list_contacts(session: AsyncSession, account_id: uuid.UUID) -> list[Contact]:
    """`API-25`. Raises `AccountNotFound`."""
    await _ensure_account(session, account_id)
    return list(
        (
            await session.execute(
                select(Contact)
                .where(Contact.account_id == account_id)
                .order_by(Contact.created_at, Contact.id)
            )
        )
        .scalars()
        .all()
    )


async def create_contact(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    full_name: str,
    job_title: str,
    source_url: str,
    persona: ContactPersona | None,
    gateway: AiGateway,
    min_p: float,
    retention_days: int,
    actor_id: uuid.UUID,
    now: datetime,
) -> Contact:
    """`API-26`. Raises `AccountNotFound`, `ContactValidationError`, and the gateway's
    `UpstreamUnavailable` or `BudgetExhausted` before anything is written."""
    for field, value in (
        ("full_name", full_name),
        ("job_title", job_title),
        ("source_url", source_url),
    ):
        _require_text(field, value)
    await _ensure_account(session, account_id)

    if persona is None:
        origin = ContactPersonaOrigin.CLASSIFIER
        persona = await _map_persona(
            gateway, job_title, min_p=min_p, account_id=account_id, actor_id=actor_id
        )
    else:
        origin = ContactPersonaOrigin.MANUAL

    contact = Contact(
        account_id=account_id,
        full_name=full_name,
        job_title=job_title,
        source_url=source_url,
        persona=persona,
        persona_origin=origin,
        retain_until=now.date() + timedelta(days=retention_days),
    )
    session.add(contact)
    await session.flush()
    await append_audit_event(
        session,
        action=AuditAction.CONTACT_CREATED,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="contact",
        entity_id=contact.id,
        payload={"account_id": str(account_id), "persona": persona.value},
    )
    await session.commit()
    return contact


async def _load_contact(session: AsyncSession, contact_id: uuid.UUID) -> Contact:
    contact = (
        await session.execute(select(Contact).where(Contact.id == contact_id).with_for_update())
    ).scalar_one_or_none()
    if contact is None:
        raise ContactNotFound(f"No contact {contact_id}.")
    return contact


async def update_contact(
    session: AsyncSession,
    *,
    contact_id: uuid.UUID,
    fields: ContactFields,
    gateway: AiGateway,
    min_p: float,
    actor_id: uuid.UUID,
    now: datetime,
) -> Contact:
    """`API-27`. A given persona is written as `MANUAL`; a changed job title remaps a
    `CLASSIFIER` persona, never a `MANUAL` one. Writes a `CONTACT_UPDATED` row with the changed
    field names only, and none when nothing changed."""
    _require_text("full_name", fields.full_name)
    _require_text("job_title", fields.job_title)
    _require_text("source_url", fields.source_url)
    contact = await _load_contact(session, contact_id)

    changes: dict[str, object] = {}
    for field in ("full_name", "job_title", "source_url"):
        value = getattr(fields, field)
        if value is not None and value != getattr(contact, field):
            changes[field] = value

    if fields.persona is not None:
        if (fields.persona, ContactPersonaOrigin.MANUAL) != (
            contact.persona,
            contact.persona_origin,
        ):
            changes["persona"] = fields.persona
            changes["persona_origin"] = ContactPersonaOrigin.MANUAL
    elif "job_title" in changes and contact.persona_origin == ContactPersonaOrigin.CLASSIFIER:
        mapped = await _map_persona(
            gateway,
            str(changes["job_title"]),
            min_p=min_p,
            account_id=contact.account_id,
            actor_id=actor_id,
        )
        if mapped != contact.persona:
            changes["persona"] = mapped

    if changes:
        for field, value in changes.items():
            setattr(contact, field, value)
        await append_audit_event(
            session,
            action=AuditAction.CONTACT_UPDATED,
            occurred_at=now,
            actor_id=actor_id,
            entity_type="contact",
            entity_id=contact.id,
            payload={"fields": sorted(changes)},
        )
    await session.commit()
    return contact


async def erase_contact(
    session: AsyncSession, *, contact_id: uuid.UUID, actor_id: uuid.UUID, now: datetime
) -> None:
    """`API-28`: [Retention and erasure](/architecture/rules.md#retention-and-erasure) on
    request. The row is deleted (drafts addressed to it lose their `contact_id` by the foreign
    key's `ON DELETE SET NULL`) and a `CONTACT_ERASED` row with reason `REQUEST` and no personal
    data is written."""
    contact = await _load_contact(session, contact_id)
    account_id = contact.account_id
    await session.delete(contact)
    await append_audit_event(
        session,
        action=AuditAction.CONTACT_ERASED,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="contact",
        entity_id=contact_id,
        payload={"account_id": str(account_id), "reason": "REQUEST"},
    )
    await session.commit()
