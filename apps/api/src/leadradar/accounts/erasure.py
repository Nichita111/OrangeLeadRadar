"""[Retention and erasure](/architecture/rules.md#retention-and-erasure): erases one contact.
The worker's housekeeping calls `erase_contact` with reason `RETENTION`; `API-28` (T21, #32) will
call it with `REQUEST`, so the rule has one implementation."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.core.enums import AuditAction
from leadradar.db.models.accounts import Contact

#: The closed pair of [Audit actions](/architecture/sql-store.md#audit-actions) `CONTACT_ERASED`
#: `reason`: erased on request, or by the housekeeping at `retain_until`.
ErasureReason = Literal["REQUEST", "RETENTION"]


async def erase_contact(
    session: AsyncSession,
    *,
    contact_id: uuid.UUID,
    reason: ErasureReason,
    now: datetime,
    actor_id: uuid.UUID | None,
) -> None:
    """Deletes the contact — its drafts lose `contact_id` through `outreach_draft`'s
    `ON DELETE SET NULL` — and appends one `CONTACT_ERASED` row with `{account_id, reason}` and
    no personal data. The caller has already found `contact_id`."""
    contact = await session.get(Contact, contact_id)
    if contact is None:
        raise LookupError(f"Contact {contact_id}, which does not exist.")
    account_id = contact.account_id
    await session.delete(contact)
    await append_audit_event(
        session,
        action=AuditAction.CONTACT_ERASED,
        occurred_at=now,
        actor_id=actor_id,
        entity_type="contact",
        entity_id=contact_id,
        payload={"account_id": str(account_id), "reason": reason},
    )
    await session.flush()
