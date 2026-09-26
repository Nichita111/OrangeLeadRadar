"""The gateway's store access: one `AI_CALL` row per call, with the AI call payload of
[Audit actions](/architecture/sql-store.md#audit-actions), through the one audit writer; and the
day's LLM spend the [Budget guard](/architecture/rules.md#budget-guard) reads from those rows."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Float, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.audit.events import append_audit_event
from leadradar.core.enums import (
    AiCallOutcome,
    AiCallProvider,
    AiRole,
    AuditAction,
    AuditEventKind,
)
from leadradar.db.models.audit import AuditEvent


@dataclass(frozen=True)
class AiCallContext:
    """What a call served, for its audit row: the passage, document, draft or run as entity,
    the run it happened in, and the user when the api makes it (the request id comes from the
    bound request context)."""

    entity_type: str | None = None
    entity_id: uuid.UUID | None = None
    run_id: uuid.UUID | None = None
    actor_id: uuid.UUID | None = None


@dataclass(frozen=True)
class AiCallRecord:
    """The AI call payload of one call."""

    ai_role: AiRole
    provider: AiCallProvider
    model: str
    prompt_version: str | None
    items: int
    input_tokens: int | None
    output_tokens: int | None
    cost_eur: float
    latency_ms: int
    outcome: AiCallOutcome
    fixture: bool

    def payload(self) -> dict[str, object]:
        return {
            "ai_role": self.ai_role.value,
            "provider": self.provider.value,
            "model": self.model,
            "prompt_version": self.prompt_version,
            "items": self.items,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cost_eur": self.cost_eur,
            "latency_ms": self.latency_ms,
            "outcome": self.outcome.value,
            "fixture": self.fixture,
        }


async def append_ai_call(
    session: AsyncSession, *, occurred_at: datetime, context: AiCallContext, record: AiCallRecord
) -> None:
    """Adds the call's `AI_CALL` row to the caller's transaction."""
    await append_audit_event(
        session,
        occurred_at=occurred_at,
        actor_id=context.actor_id,
        action=AuditAction.AI_CALL,
        entity_type=context.entity_type,
        entity_id=context.entity_id,
        payload=record.payload(),
        run_id=context.run_id,
    )


async def read_llm_spend_eur(session: AsyncSession, *, since: datetime, until: datetime) -> float:
    """Sum of `cost_eur` of the `AI_CALL` rows with provider `OPENROUTER` in `[since, until)`."""
    total = (
        await session.execute(
            select(func.sum(cast(AuditEvent.payload["cost_eur"].astext, Float))).where(
                AuditEvent.kind == AuditEventKind.AI_CALL,
                AuditEvent.payload["provider"].astext == AiCallProvider.OPENROUTER.value,
                AuditEvent.occurred_at >= since,
                AuditEvent.occurred_at < until,
            )
        )
    ).scalar_one()
    return 0.0 if total is None else float(total)
