"""Router of the [Feedback and alerts](/architecture/interfaces.md#feedback-and-alerts) family:
`API-46` to `API-49`. `API-47`'s response is [`FindingView`](prospects_and_evidence.py); every
route is a declared stub answering `501 NOT_IMPLEMENTED`."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from leadradar.api.common import IdName, Page
from leadradar.api.prospects_and_evidence import FindingView, LeadFeedback
from leadradar.api.router_utils import stub_router
from leadradar.core.enums import (
    AccountScoreBand,
    AlertKind,
    FindingFeedbackVerdict,
    FindingStrength,
    LeadFeedbackVerdict,
)

router = stub_router("feedback-and-alerts")


class FeedbackCreate(BaseModel):
    """[`FeedbackCreate`](/architecture/interfaces.md#feedbackcreate)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    verdict: LeadFeedbackVerdict
    note: str | None = None


class FindingFeedbackCreate(BaseModel):
    """`FeedbackCreate` specialized for `API-47`'s finding verdicts."""

    model_config = ConfigDict(extra="forbid", frozen=True, title="FeedbackCreate")

    verdict: FindingFeedbackVerdict
    note: str | None = None


class AlertFinding(BaseModel):
    """`AlertView.finding`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    question_text: str
    strength: FindingStrength
    quote: str | None


class AlertBandChange(BaseModel):
    """`AlertView.band_change`."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_: AccountScoreBand = Field(alias="from")
    to: AccountScoreBand


class AlertView(BaseModel):
    """[`AlertView`](/architecture/interfaces.md#alertview)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    created_at: str
    acknowledged_at: str | None
    kind: AlertKind
    account: IdName
    service: IdName
    finding: AlertFinding | None
    band_change: AlertBandChange | None
    acknowledged_by_name: str | None


@router.post("/accounts/{id}/scores/{service_id}/feedback", response_model=LeadFeedback)
async def create_lead_feedback(id: str, service_id: str, payload: FeedbackCreate) -> LeadFeedback:
    """`API-46`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/findings/{id}/feedback", response_model=FindingView)
async def create_finding_feedback(id: str, payload: FindingFeedbackCreate) -> FindingView:
    """`API-47`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.get("/alerts", response_model=Page[AlertView])
async def list_alerts(
    service_id: str | None = None,
    unread: bool | None = None,
    page: int = 1,
    page_size: int | None = None,
) -> Page[AlertView]:
    """`API-48`."""
    raise AssertionError("unreachable: contract_not_built already raised")


@router.post("/alerts/{id}/acknowledge", response_model=AlertView)
async def acknowledge_alert(id: str) -> AlertView:
    """`API-49`."""
    raise AssertionError("unreachable: contract_not_built already raised")
