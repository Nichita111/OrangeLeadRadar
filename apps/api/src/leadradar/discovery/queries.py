"""Reads that shape [`DiscoveryCandidate`](/architecture/interfaces.md#discoverycandidate)
(`API-30`) out of the store. Plain dataclasses; the Pydantic response model lives at the api
boundary (`api/discovery.py`)."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.core.enums import DiscoveryCandidateOrigin, DiscoveryCandidateStatus
from leadradar.db.models.accounts import DiscoveryCandidate
from leadradar.db.models.ingestion import Document
from leadradar.discovery.errors import CandidateNotFound


@dataclass(frozen=True)
class CandidateEvidence:
    """`DiscoveryCandidate.evidence`: the `NEWS_MENTION` document that named the company."""

    document_id: uuid.UUID
    title: str | None
    url: str
    published_at: datetime | None
    quote: str


@dataclass(frozen=True)
class DiscoveryCandidateView:
    """[`DiscoveryCandidate`](/architecture/interfaces.md#discoverycandidate)."""

    id: uuid.UUID
    service_id: uuid.UUID
    name: str
    domain: str | None
    country_code: str | None
    industry: str | None
    employee_count: int | None
    origin: DiscoveryCandidateOrigin
    status: DiscoveryCandidateStatus
    fit_estimate: int
    evidence: CandidateEvidence | None
    reject_reason: str | None
    account_id: uuid.UUID | None


@dataclass(frozen=True)
class PageData[ItemT]:
    """`Page<T>` ([Conventions](/architecture/interfaces.md#conventions) Pagination)."""

    items: tuple[ItemT, ...]
    page: int
    page_size: int
    total: int


def _view(candidate: DiscoveryCandidate, document: Document | None) -> DiscoveryCandidateView:
    evidence = None
    if document is not None and candidate.quote is not None:
        evidence = CandidateEvidence(
            document_id=document.id,
            title=document.title,
            url=document.url,
            published_at=document.published_at,
            quote=candidate.quote,
        )
    return DiscoveryCandidateView(
        id=candidate.id,
        service_id=candidate.service_id,
        name=candidate.name,
        domain=candidate.domain,
        country_code=candidate.country_code,
        industry=candidate.industry,
        employee_count=candidate.employee_count,
        origin=candidate.origin,
        status=candidate.status,
        fit_estimate=candidate.fit_estimate,
        evidence=evidence,
        reject_reason=candidate.reject_reason,
        account_id=candidate.account_id,
    )


async def list_candidates(
    session: AsyncSession,
    *,
    service_id: uuid.UUID,
    status: DiscoveryCandidateStatus | None,
    page: int,
    page_size: int,
) -> PageData[DiscoveryCandidateView]:
    """`API-30`: ordered by `fit_estimate` descending ([Discovery contracts]
    (/architecture/interfaces.md#discovery-contracts))."""
    filters = [DiscoveryCandidate.service_id == service_id]
    if status is not None:
        filters.append(DiscoveryCandidate.status == status)

    total = (
        await session.execute(select(func.count()).select_from(DiscoveryCandidate).where(*filters))
    ).scalar_one()

    rows = (
        await session.execute(
            select(DiscoveryCandidate, Document)
            .outerjoin(Document, Document.id == DiscoveryCandidate.document_id)
            .where(*filters)
            .order_by(DiscoveryCandidate.fit_estimate.desc(), DiscoveryCandidate.created_at)
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()

    items = tuple(_view(candidate, document) for candidate, document in rows)
    return PageData(items=items, page=page, page_size=page_size, total=total)


async def get_candidate(session: AsyncSession, candidate_id: uuid.UUID) -> DiscoveryCandidateView:
    """The candidate's view, joined to its evidence document. Raises `CandidateNotFound`."""
    row = (
        await session.execute(
            select(DiscoveryCandidate, Document)
            .outerjoin(Document, Document.id == DiscoveryCandidate.document_id)
            .where(DiscoveryCandidate.id == candidate_id)
        )
    ).first()
    if row is None:
        raise CandidateNotFound(f"No discovery candidate {candidate_id}.")
    return _view(row[0], row[1])
