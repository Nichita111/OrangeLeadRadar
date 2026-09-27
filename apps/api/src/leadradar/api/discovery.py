"""Router of the [Discovery](/architecture/interfaces.md#discovery) family: `API-29` to `API-32`."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi import status as http_status
from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.json_schema import SkipJsonSchema
from sqlalchemy.ext.asyncio import AsyncSession

from leadradar.api.accounts import Account, to_account
from leadradar.api.authentication import CurrentUser
from leadradar.api.pagination import Page, PageRequest, page_request
from leadradar.api.runs_and_source_plugins import Run, plugins_with_a_key, to_run
from leadradar.core.enums import DiscoveryCandidateOrigin, DiscoveryCandidateStatus
from leadradar.db.session import get_session
from leadradar.discovery.commands import accept_candidate, reject_candidate, request_discovery_run
from leadradar.discovery.queries import DiscoveryCandidateView, list_candidates

router = APIRouter(tags=["discovery"])


class DiscoveryCandidateEvidence(BaseModel):
    """`DiscoveryCandidate.evidence`: the `NEWS_MENTION` document that named the company."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    title: str | None
    url: str
    published_at: str | None
    quote: str


class DiscoveryCandidate(BaseModel):
    """[`DiscoveryCandidate`](/architecture/interfaces.md#discoverycandidate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    service_id: str
    name: str
    domain: str | None
    country_code: str | None
    industry: str | None
    employee_count: int | None
    origin: DiscoveryCandidateOrigin
    status: DiscoveryCandidateStatus
    fit_estimate: int
    evidence: DiscoveryCandidateEvidence | None
    reject_reason: str | None
    account_id: str | None


class CandidateDecision(BaseModel):
    """[`CandidateDecision`](/architecture/interfaces.md#candidatedecision)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    domain: str | SkipJsonSchema[None] = None
    reason: str | SkipJsonSchema[None] = None

    @field_validator("domain", "reason", mode="before")
    @classmethod
    def _optional_field_is_not_null(cls, value: object) -> object:
        if value is None:
            raise ValueError("Omit this field instead of sending null.")
        return value


def _to_candidate(view: DiscoveryCandidateView) -> DiscoveryCandidate:
    evidence = None
    if view.evidence is not None:
        evidence = DiscoveryCandidateEvidence(
            document_id=str(view.evidence.document_id),
            title=view.evidence.title,
            url=view.evidence.url,
            published_at=(
                view.evidence.published_at.isoformat() if view.evidence.published_at else None
            ),
            quote=view.evidence.quote,
        )
    return DiscoveryCandidate(
        id=str(view.id),
        service_id=str(view.service_id),
        name=view.name,
        domain=view.domain,
        country_code=view.country_code,
        industry=view.industry,
        employee_count=view.employee_count,
        origin=view.origin,
        status=view.status,
        fit_estimate=view.fit_estimate,
        evidence=evidence,
        reject_reason=view.reject_reason,
        account_id=str(view.account_id) if view.account_id is not None else None,
    )


@router.post(
    "/services/{id}/discovery-runs",
    status_code=http_status.HTTP_202_ACCEPTED,
    responses={
        http_status.HTTP_200_OK: {"model": Run, "description": "The discovery already queued"}
    },
)
async def start_discovery_run(
    id: uuid.UUID,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> Run:
    """`API-29`: `202` with a new discovery run, or `200` with the one already queued or
    running. Raises `ServiceNotFound`, `ServiceNotActive`, `NoActiveScoringVersion` (G7)."""
    result = await request_discovery_run(
        session, service_id=id, principal=principal, now=request.app.state.clock()
    )
    if not result.created:
        response.status_code = http_status.HTTP_200_OK
    return to_run(result.run)


@router.get("/discovery-candidates")
async def list_discovery_candidates(
    session: Annotated[AsyncSession, Depends(get_session)],
    _principal: CurrentUser,
    paging: Annotated[PageRequest, Depends(page_request)],
    service_id: uuid.UUID,
    status: DiscoveryCandidateStatus | None = None,
) -> Page[DiscoveryCandidate]:
    """`API-30`: a service's discovery candidates, ordered by `fit_estimate` descending, then by
    the naming article's `published_at` newest first and unknown last, then by
    `normalised_name`."""
    result = await list_candidates(
        session,
        service_id=service_id,
        status=status,
        page=paging.page,
        page_size=paging.page_size,
    )
    return Page[DiscoveryCandidate](
        items=[_to_candidate(item) for item in result.items],
        page=result.page,
        page_size=result.page_size,
        total=result.total,
    )


@router.post("/discovery-candidates/{id}/accept")
async def accept_discovery_candidate(
    id: uuid.UUID,
    payload: CandidateDecision,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> Account:
    """`API-31`: `payload.domain` is used only when the candidate has none. Raises
    `CandidateNotFound`, `CandidateNotPending`, `CandidateDomainRequired`,
    `create_discovered_account`'s own errors (`InvalidAccountDomain`, `DomainConflict`,
    `UnknownIndustry`)."""
    result = await accept_candidate(
        session,
        candidate_id=id,
        domain=payload.domain,
        keys_configured=plugins_with_a_key(request.app.state.settings),
        principal=principal,
        now=request.app.state.clock(),
    )
    return to_account(result)


@router.post("/discovery-candidates/{id}/reject")
async def reject_discovery_candidate(
    id: uuid.UUID,
    payload: CandidateDecision,
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    principal: CurrentUser,
) -> DiscoveryCandidate:
    """`API-32`: `payload.reason` becomes `reject_reason`. Raises `CandidateNotFound`,
    `CandidateNotPending`."""
    result = await reject_candidate(
        session,
        candidate_id=id,
        reason=payload.reason,
        principal=principal,
        now=request.app.state.clock(),
    )
    return _to_candidate(result)
