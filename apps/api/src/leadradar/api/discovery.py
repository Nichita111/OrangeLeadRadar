"""Router of the [Discovery](/architecture/interfaces.md#discovery) family: `API-29` to `API-32`.
Every route is a declared stub answering `501 NOT_IMPLEMENTED`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from leadradar.api.accounts_and_contacts import Account
from leadradar.api.common import Page
from leadradar.api.router_utils import stub_router
from leadradar.api.runs_and_plugins import Run
from leadradar.core.enums import DiscoveryCandidateOrigin, DiscoveryCandidateStatus

router = stub_router("discovery")


class DiscoveryCandidateEvidence(BaseModel):
    """`DiscoveryCandidate.evidence`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    document_id: str
    title: str
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

    domain: str | None = None
    reason: str | None = None


@router.post("/services/{id}/discovery-runs", response_model=Run, status_code=202)
async def start_discovery_run(id: str) -> Run:
    """`API-29`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/discovery-candidates", response_model=Page[DiscoveryCandidate])
async def list_discovery_candidates(
    service_id: str,
    status: DiscoveryCandidateStatus | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> Page[DiscoveryCandidate]:
    """`API-30`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/discovery-candidates/{id}/accept", response_model=Account)
async def accept_discovery_candidate(id: str, payload: CandidateDecision) -> Account:
    """`API-31`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/discovery-candidates/{id}/reject", response_model=DiscoveryCandidate)
async def reject_discovery_candidate(id: str, payload: CandidateDecision) -> DiscoveryCandidate:
    """`API-32`."""
    raise AssertionError("unreachable: contract_not_built already raised")
