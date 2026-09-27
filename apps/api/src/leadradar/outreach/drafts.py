"""`API-56` to `API-58` (`S-OUT-01`): generates an email or LinkedIn InMail draft for an account
and service by [Outreach grounding](/architecture/rules.md#outreach-grounding) through the AI
gateway, lists an account's drafts, and edits or exports one. Nothing is ever sent: a draft is
stored for a person to copy or download ([RULE-06](/requirements/business.md#business-rules)).
Each function owns its own transaction."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.ai.audit import AiCallContext
from leadradar.ai.errors import UpstreamUnavailable
from leadradar.ai.gateway import AiGateway
from leadradar.ai.shapes import (
    OutreachContact,
    OutreachFinding,
    OutreachInput,
    OutreachOutput,
    OutreachPreferences,
    OutreachProviderFact,
    OutreachService,
    ToneCheckInput,
    ToneCheckOutput,
)
from leadradar.audit.events import append_audit_event
from leadradar.core.enums import (
    AuditAction,
    Dependency,
    EngagementOrigin,
    EngagementStatus,
    FindingStatus,
    OutreachDraftChannel,
    OutreachDraftStatus,
    OutreachPersonalization,
    ProviderFactStatus,
)
from leadradar.core.outreach_grounding import grounding_violations
from leadradar.db.models.accounts import Account, Contact
from leadradar.db.models.configuration import ProviderFact, Service, SignalQuestion
from leadradar.db.models.identity import AppUser
from leadradar.db.models.ingestion import Chunk, Document
from leadradar.db.models.outreach import EngagementStatusRow, OutreachDraft
from leadradar.db.models.signals import AccountScore, Finding
from leadradar.outreach.company_push import intent_question_entries, top_finding_ids
from leadradar.outreach.errors import OutreachNotFound, OutreachValidationError

#: [Outreach grounding](/architecture/rules.md#outreach-grounding): "An invalid output is
#: requested once more".
_ATTEMPTS = 2


@dataclass(frozen=True)
class DraftFindingView:
    id: uuid.UUID
    question_text: str
    quote: str


@dataclass(frozen=True)
class DraftContactView:
    id: uuid.UUID
    full_name: str
    job_title: str


@dataclass(frozen=True)
class DraftProviderFactView:
    id: uuid.UUID
    text: str


@dataclass(frozen=True)
class DraftView:
    """[`OutreachDraft`](/architecture/interfaces.md#outreachdraft)."""

    id: uuid.UUID
    account_id: uuid.UUID
    service_id: uuid.UUID
    subject: str | None
    body: str
    edited: bool
    created_at: datetime
    channel: OutreachDraftChannel
    status: OutreachDraftStatus
    preferences: OutreachPreferences | None
    contact: DraftContactView | None
    findings: list[DraftFindingView]
    provider_facts: list[DraftProviderFactView]
    created_by_name: str


@dataclass(frozen=True)
class EngagementView:
    id: uuid.UUID
    service_id: uuid.UUID
    status: EngagementStatus
    origin: EngagementOrigin
    occurred_at: datetime
    note: str | None
    created_at: datetime
    set_by_name: str | None


@dataclass(frozen=True)
class _GroundingFinding:
    id: uuid.UUID
    question_text: str
    quote: str
    quote_en: str | None
    observed_at: datetime
    url: str
    language: str


@dataclass(frozen=True)
class _GroundingProviderFact:
    id: uuid.UUID
    text: str


async def _provider_facts(
    session: AsyncSession, service_id: uuid.UUID, limit: int
) -> list[_GroundingProviderFact]:
    rows = (
        (
            await session.execute(
                select(ProviderFact)
                .where(ProviderFact.status == ProviderFactStatus.ACTIVE)
                .order_by(ProviderFact.created_at.desc(), ProviderFact.id)
            )
        )
        .scalars()
        .all()
    )
    applicable = [row for row in rows if not row.service_ids or service_id in row.service_ids]
    applicable.sort(key=lambda row: service_id not in row.service_ids)
    return [_GroundingProviderFact(row.id, row.text) for row in applicable[:limit]]


async def _grounding_findings(
    session: AsyncSession, account_id: uuid.UUID, service_id: uuid.UUID, limit: int
) -> list[_GroundingFinding]:
    """Up to `limit` in-force findings of the service's positive questions, most `points` in the
    current breakdown first, by the one selection `top_finding_ids` owns."""
    breakdown = (
        await session.execute(
            select(AccountScore.breakdown).where(
                AccountScore.account_id == account_id,
                AccountScore.service_id == service_id,
                AccountScore.is_current.is_(True),
            )
        )
    ).scalar_one_or_none()
    if not isinstance(breakdown, dict):
        return []
    entries = [
        entry
        for entry in intent_question_entries(breakdown)
        if isinstance(entry, dict) and isinstance(entry.get("finding_id"), str)
    ]
    if not entries:
        return []
    rows = (
        await session.execute(
            select(
                Finding.id,
                SignalQuestion.text,
                Finding.quote,
                Finding.quote_en,
                Finding.observed_at,
                Document.url,
                Document.language,
            )
            .join(SignalQuestion, SignalQuestion.id == Finding.question_id)
            .join(Chunk, Chunk.id == Finding.chunk_id)
            .join(Document, Document.id == Chunk.document_id)
            .where(
                Finding.id.in_([uuid.UUID(str(entry["finding_id"])) for entry in entries]),
                Finding.account_id == account_id,
                Finding.status == FindingStatus.ACTIVE,
            )
        )
    ).all()
    by_id = {str(row[0]): _GroundingFinding(*row) for row in rows}
    in_force = {"intent": {"questions": [e for e in entries if e["finding_id"] in by_id]}}
    observed_at = {key: finding.observed_at for key, finding in by_id.items()}
    return [by_id[key] for key in top_finding_ids(in_force, observed_at, limit)]


def _output_violations(
    output: OutreachOutput,
    channel: OutreachDraftChannel,
    findings: Sequence[_GroundingFinding],
    provider_facts: Sequence[_GroundingProviderFact],
    preferences: OutreachPreferences | None,
    max_chars: int,
) -> list[str]:
    violations = grounding_violations(
        subject=output.subject,
        body=output.body,
        cited_ids=output.cited_finding_ids,
        url_by_finding={str(finding.id): finding.url for finding in findings},
        max_chars=max_chars,
    )
    if channel == OutreachDraftChannel.EMAIL and not (output.subject or "").strip():
        violations.append("an email has no subject")
    finding_ids = {str(finding.id) for finding in findings}
    fact_ids = {str(fact.id) for fact in provider_facts}
    cited_findings = set(output.cited_finding_ids)
    if not cited_findings <= finding_ids:
        violations.append("a cited finding was not supplied")
    if not set(output.cited_provider_fact_ids) <= fact_ids:
        violations.append("a cited provider fact was not supplied")
    expected = (
        1
        if preferences is not None
        and preferences.personalization == OutreachPersonalization.STANDARD
        else 2
        if preferences is not None
        and preferences.personalization == OutreachPersonalization.TAILORED
        else None
    )
    if expected is not None and len(cited_findings) != expected:
        violations.append(f"personalization requires exactly {expected} cited findings")
    return violations


async def _views(session: AsyncSession, drafts: Sequence[OutreachDraft]) -> list[DraftView]:
    finding_ids = {finding_id for draft in drafts for finding_id in draft.finding_ids}
    contact_ids = {draft.contact_id for draft in drafts if draft.contact_id is not None}
    provider_fact_ids = {fact_id for draft in drafts for fact_id in draft.provider_fact_ids}
    user_ids = {draft.created_by for draft in drafts}
    findings = {
        row[0]: DraftFindingView(*row)
        for row in (
            await session.execute(
                select(Finding.id, SignalQuestion.text, Finding.quote)
                .join(SignalQuestion, SignalQuestion.id == Finding.question_id)
                .where(Finding.id.in_(list(finding_ids)))
            )
        ).all()
    }
    contacts = {
        row[0]: DraftContactView(*row)
        for row in (
            await session.execute(
                select(Contact.id, Contact.full_name, Contact.job_title).where(
                    Contact.id.in_(list(contact_ids))
                )
            )
        ).all()
    }
    provider_facts = {
        row[0]: DraftProviderFactView(*row)
        for row in (
            await session.execute(
                select(ProviderFact.id, ProviderFact.text).where(
                    ProviderFact.id.in_(list(provider_fact_ids))
                )
            )
        ).all()
    }
    names = {
        user_id: display_name
        for user_id, display_name in (
            await session.execute(
                select(AppUser.id, AppUser.display_name).where(AppUser.id.in_(list(user_ids)))
            )
        ).all()
    }
    return [
        DraftView(
            id=draft.id,
            account_id=draft.account_id,
            service_id=draft.service_id,
            subject=draft.subject,
            body=draft.body,
            edited=draft.edited,
            created_at=draft.created_at,
            channel=draft.channel,
            status=draft.status,
            preferences=(
                None
                if draft.preferences is None
                else OutreachPreferences.model_validate(draft.preferences)
            ),
            contact=contacts.get(draft.contact_id) if draft.contact_id is not None else None,
            findings=[findings[i] for i in draft.finding_ids if i in findings],
            provider_facts=[
                provider_facts[i] for i in draft.provider_fact_ids if i in provider_facts
            ],
            created_by_name=names.get(draft.created_by, ""),
        )
        for draft in drafts
    ]


async def create_draft(
    session: AsyncSession,
    *,
    account_id: uuid.UUID,
    service_id: uuid.UUID,
    channel: OutreachDraftChannel,
    contact_id: uuid.UUID | None,
    preferences: OutreachPreferences | None,
    gateway: AiGateway,
    max_findings: int,
    max_chars: int,
    max_provider_facts: int,
    principal: AppUser,
    now: datetime,
) -> DraftView:
    """`API-56`. Raises `OutreachNotFound` for an unknown account or service,
    `OutreachValidationError` for a contact of another account or an account without an in-force
    positive finding for the service, and the gateway's `BudgetExhausted` or
    `UpstreamUnavailable` (`INVALID_OUTPUT` after a second invalid output)."""
    account_name = (
        await session.execute(select(Account.name).where(Account.id == account_id))
    ).scalar_one_or_none()
    if account_name is None:
        raise OutreachNotFound(f"No account {account_id}.")
    service = (
        await session.execute(select(Service).where(Service.id == service_id))
    ).scalar_one_or_none()
    if service is None:
        raise OutreachNotFound(f"No service {service_id}.")

    contact: Contact | None = None
    if contact_id is not None:
        contact = (
            await session.execute(
                select(Contact).where(Contact.id == contact_id, Contact.account_id == account_id)
            )
        ).scalar_one_or_none()
        if contact is None:
            raise OutreachValidationError("contact_id", "Not a contact of this account.")

    findings = await _grounding_findings(session, account_id, service_id, max_findings)
    if not findings:
        raise OutreachValidationError(
            "service_id", "The account has no in-force positive finding for the service."
        )
    if preferences is not None:
        if preferences.personalization == OutreachPersonalization.TAILORED:
            if len(findings) < 2:
                raise OutreachValidationError(
                    "preferences.personalization", "Tailored needs at least two eligible signals."
                )
            findings = findings[:2]
        elif preferences.personalization == OutreachPersonalization.STANDARD:
            findings = findings[:1]
        elif contact is None:
            raise OutreachValidationError(
                "preferences.personalization", "Bespoke needs a selected contact."
            )

    provider_facts = await _provider_facts(session, service_id, max_provider_facts)

    role_input = OutreachInput(
        account_name=account_name,
        service=OutreachService(name=service.name, value_proposition=service.value_proposition),
        findings=[
            OutreachFinding(
                id=str(finding.id),
                question_text=finding.question_text,
                quote=finding.quote,
                quote_en=finding.quote_en,
                observed_at=finding.observed_at,
                url=finding.url,
                language=finding.language,
            )
            for finding in findings
        ],
        provider_facts=[
            OutreachProviderFact(id=str(fact.id), text=fact.text) for fact in provider_facts
        ],
        contact=(
            None
            if contact is None
            else OutreachContact(
                full_name=contact.full_name, job_title=contact.job_title, persona=contact.persona
            )
        ),
        channel=channel,
        sender_name=principal.display_name,
        preferences=preferences,
    )
    context = AiCallContext(entity_type="account", entity_id=account_id, actor_id=principal.id)
    output: OutreachOutput | None = None
    for _ in range(_ATTEMPTS):
        candidate = await gateway.draft_outreach(role_input, context)
        if not _output_violations(
            candidate, channel, findings, provider_facts, preferences, max_chars
        ):
            output = candidate
            break
    if output is None:
        raise UpstreamUnavailable(
            Dependency.LLM, "INVALID_OUTPUT", "The outreach draft broke the grounding rule twice"
        )

    cited = [uuid.UUID(finding_id) for finding_id in dict.fromkeys(output.cited_finding_ids)]
    cited_facts = [uuid.UUID(fact_id) for fact_id in dict.fromkeys(output.cited_provider_fact_ids)]
    draft = OutreachDraft(
        account_id=account_id,
        service_id=service_id,
        contact_id=contact_id,
        channel=channel,
        subject=output.subject if channel == OutreachDraftChannel.EMAIL else None,
        body=output.body,
        finding_ids=cited,
        provider_fact_ids=cited_facts,
        preferences=None if preferences is None else preferences.model_dump(mode="json"),
        edited=False,
        status=OutreachDraftStatus.DRAFT,
        created_by=principal.id,
    )
    session.add(draft)
    await session.flush()
    await session.refresh(draft)
    await append_audit_event(
        session,
        action=AuditAction.DRAFT_CREATED,
        occurred_at=now,
        actor_id=principal.id,
        entity_type="outreach_draft",
        entity_id=draft.id,
        payload={
            "channel": channel.value,
            "finding_ids": [str(i) for i in cited],
            "provider_fact_ids": [str(i) for i in cited_facts],
        },
    )
    [view] = await _views(session, [draft])
    await session.commit()
    return view


async def list_drafts(
    session: AsyncSession, account_id: uuid.UUID, service_id: uuid.UUID
) -> list[DraftView]:
    """`API-57`: the account's drafts for the service, newest first."""
    drafts = (
        (
            await session.execute(
                select(OutreachDraft)
                .where(
                    OutreachDraft.account_id == account_id,
                    OutreachDraft.service_id == service_id,
                )
                .order_by(OutreachDraft.created_at.desc(), OutreachDraft.id)
            )
        )
        .scalars()
        .all()
    )
    return await _views(session, drafts)


async def update_draft(
    session: AsyncSession,
    *,
    draft_id: uuid.UUID,
    subject: str | None,
    body: str | None,
    status: OutreachDraftStatus | None,
    actor_id: uuid.UUID,
    now: datetime,
) -> DraftView:
    """`API-58`: changing `subject` or `body` sets `edited` and writes `DRAFT_UPDATED` with the
    changed field names; `status` may only move to `EXPORTED`, which writes `DRAFT_EXPORTED`."""
    draft = (
        await session.execute(
            select(OutreachDraft).where(OutreachDraft.id == draft_id).with_for_update()
        )
    ).scalar_one_or_none()
    if draft is None:
        raise OutreachNotFound(f"No outreach draft {draft_id}.")
    if subject is not None and draft.channel != OutreachDraftChannel.EMAIL:
        raise OutreachValidationError("subject", "Only an email has a subject.")
    if status is not None and status != draft.status and status != OutreachDraftStatus.EXPORTED:
        raise OutreachValidationError("status", "status may only move to EXPORTED.")

    changed = [
        field
        for field, value in (("subject", subject), ("body", body))
        if value is not None and value != getattr(draft, field)
    ]
    if changed:
        for field in changed:
            setattr(draft, field, subject if field == "subject" else body)
        draft.edited = True
        await append_audit_event(
            session,
            action=AuditAction.DRAFT_UPDATED,
            occurred_at=now,
            actor_id=actor_id,
            entity_type="outreach_draft",
            entity_id=draft.id,
            payload={"fields": changed},
        )
    if status == OutreachDraftStatus.EXPORTED and draft.status != OutreachDraftStatus.EXPORTED:
        draft.status = OutreachDraftStatus.EXPORTED
        await append_audit_event(
            session,
            action=AuditAction.DRAFT_EXPORTED,
            occurred_at=now,
            actor_id=actor_id,
            entity_type="outreach_draft",
            entity_id=draft.id,
            payload={},
        )
    await session.flush()
    await session.refresh(draft)
    [view] = await _views(session, [draft])
    await session.commit()
    return view


async def check_tone(
    session: AsyncSession,
    *,
    draft_id: uuid.UUID,
    subject: str | None,
    body: str,
    gateway: AiGateway,
    actor_id: uuid.UUID,
) -> ToneCheckOutput:
    """`API-91`: checks current editor text without changing the draft."""
    draft = (
        await session.execute(select(OutreachDraft).where(OutreachDraft.id == draft_id))
    ).scalar_one_or_none()
    if draft is None:
        raise OutreachNotFound(f"No outreach draft {draft_id}.")
    if draft.channel == OutreachDraftChannel.EMAIL and not (subject or "").strip():
        raise OutreachValidationError("subject", "An email needs a subject.")
    if draft.channel == OutreachDraftChannel.LINKEDIN_INMAIL and subject is not None:
        raise OutreachValidationError("subject", "LinkedIn InMail has no subject.")
    preferences = (
        None if draft.preferences is None else OutreachPreferences.model_validate(draft.preferences)
    )
    return await gateway.check_outreach_tone(
        ToneCheckInput(
            channel=draft.channel,
            preferences=preferences,
            subject=subject,
            body=body,
        ),
        AiCallContext(entity_type="outreach_draft", entity_id=draft.id, actor_id=actor_id),
    )


async def mark_contacted(
    session: AsyncSession,
    *,
    draft_id: uuid.UUID,
    principal: AppUser,
    now: datetime,
) -> EngagementView:
    """`API-93`: atomically marks an exported draft contacted without downgrading a later status."""
    draft = (
        await session.execute(
            select(OutreachDraft).where(OutreachDraft.id == draft_id).with_for_update()
        )
    ).scalar_one_or_none()
    if draft is None:
        raise OutreachNotFound(f"No outreach draft {draft_id}.")
    if draft.status != OutreachDraftStatus.EXPORTED:
        raise OutreachValidationError("status", "Export the draft before marking it contacted.")
    current = (
        await session.execute(
            select(EngagementStatusRow)
            .where(
                EngagementStatusRow.account_id == draft.account_id,
                EngagementStatusRow.service_id == draft.service_id,
            )
            .order_by(EngagementStatusRow.occurred_at.desc(), EngagementStatusRow.created_at.desc())
            .limit(1)
            .with_for_update()
        )
    ).scalar_one_or_none()
    if current is not None:
        if current.status != EngagementStatus.CONTACTED:
            setter = (
                None
                if current.set_by is None
                else (
                    await session.execute(
                        select(AppUser.display_name).where(AppUser.id == current.set_by)
                    )
                ).scalar_one_or_none()
            )
            view = EngagementView(
                current.id,
                current.service_id,
                current.status,
                current.origin,
                current.occurred_at,
                current.note,
                current.created_at,
                setter,
            )
        else:
            view = EngagementView(
                current.id,
                current.service_id,
                current.status,
                current.origin,
                current.occurred_at,
                current.note,
                current.created_at,
                principal.display_name if current.set_by == principal.id else None,
            )
        await session.commit()
        return view
    row = EngagementStatusRow(
        account_id=draft.account_id,
        service_id=draft.service_id,
        status=EngagementStatus.CONTACTED,
        origin=EngagementOrigin.MANUAL,
        set_by=principal.id,
        occurred_at=now,
        note=None,
    )
    session.add(row)
    await session.flush()
    await session.refresh(row)
    await append_audit_event(
        session,
        action=AuditAction.ENGAGEMENT_SET,
        occurred_at=now,
        actor_id=principal.id,
        entity_type="engagement_status",
        entity_id=row.id,
        payload={"status": row.status.value, "service_id": str(row.service_id)},
    )
    await session.commit()
    return EngagementView(
        row.id,
        row.service_id,
        row.status,
        row.origin,
        row.occurred_at,
        row.note,
        row.created_at,
        principal.display_name,
    )
