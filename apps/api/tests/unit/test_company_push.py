"""Unit tests of `outreach.company_push`: the pure selection and assembly of
[`CompanyPush`](/architecture/interfaces.md#companypush) (`API-59`)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from leadradar.core.enums import AccountScoreBand, AccountScoreStanding
from leadradar.outreach.company_push import (
    TopSignalText,
    account_detail_url,
    build_company_push,
    top_finding_ids,
    top_signal_lines,
)

pytestmark = pytest.mark.unit


def _breakdown(entries: list[dict[str, object]]) -> dict[str, object]:
    return {"intent": {"questions": entries}}


def _entry(finding_id: str, points: float, polarity: str = "POSITIVE") -> dict[str, object]:
    return {"finding_id": finding_id, "points": points, "polarity": polarity}


# --- top_finding_ids ------------------------------------------------------------------------


def test_orders_positive_findings_by_most_points_first() -> None:
    low, high = str(uuid.uuid4()), str(uuid.uuid4())
    breakdown = _breakdown([_entry(low, 10.0), _entry(high, 50.0)])
    observed_at = {
        low: datetime(2026, 1, 1, tzinfo=UTC),
        high: datetime(2026, 1, 1, tzinfo=UTC),
    }

    assert top_finding_ids(breakdown, observed_at, limit=5) == [high, low]


@pytest.mark.parametrize("count,limit,expected_length", [(2, 5, 2), (3, 3, 3), (4, 2, 2)])
def test_respects_the_limit_boundary(count: int, limit: int, expected_length: int) -> None:
    ids = [str(uuid.uuid4()) for _ in range(count)]
    breakdown = _breakdown([_entry(fid, float(i)) for i, fid in enumerate(ids)])
    observed_at = {fid: datetime(2026, 1, 1, tzinfo=UTC) for fid in ids}

    assert len(top_finding_ids(breakdown, observed_at, limit=limit)) == expected_length


def test_breaks_a_points_tie_by_observed_at_descending() -> None:
    older, newer = str(uuid.uuid4()), str(uuid.uuid4())
    breakdown = _breakdown([_entry(older, 20.0), _entry(newer, 20.0)])
    observed_at = {
        older: datetime(2026, 1, 1, tzinfo=UTC),
        newer: datetime(2026, 2, 1, tzinfo=UTC),
    }

    assert top_finding_ids(breakdown, observed_at, limit=5) == [newer, older]


def test_never_selects_a_negative_questions_finding() -> None:
    positive, negative = str(uuid.uuid4()), str(uuid.uuid4())
    breakdown = _breakdown([_entry(positive, 5.0, "POSITIVE"), _entry(negative, 99.0, "NEGATIVE")])
    observed_at = {
        positive: datetime(2026, 1, 1, tzinfo=UTC),
        negative: datetime(2026, 1, 1, tzinfo=UTC),
    }

    assert top_finding_ids(breakdown, observed_at, limit=5) == [positive]


# --- top_signal_lines ------------------------------------------------------------------------


def test_no_positive_finding_yields_an_empty_string_not_a_placeholder() -> None:
    assert top_signal_lines([]) == ""


def test_each_signal_is_one_line_question_text_dash_quote_joined_by_newline() -> None:
    signals = [
        TopSignalText(
            question_text="Does it announce a cost-reduction programme?", quote="We cut costs."
        ),
        TopSignalText(question_text="Is there a hiring push?", quote="We are hiring."),
    ]

    result = top_signal_lines(signals)

    assert result == (
        'Does it announce a cost-reduction programme? — "We cut costs."\n'
        'Is there a hiring push? — "We are hiring."'
    )


# --- account_detail_url ----------------------------------------------------------------------


@pytest.mark.parametrize("app_base_url", ["http://localhost:8080", "http://localhost:8080/"])
def test_joins_app_base_url_and_the_account_id_with_no_double_slash(app_base_url: str) -> None:
    account_id = uuid.uuid4()

    url = account_detail_url(app_base_url, account_id)

    assert url == f"http://localhost:8080/accounts/{account_id}"
    assert "//accounts" not in url.replace("http://", "")


# --- build_company_push ----------------------------------------------------------------------


def test_carries_domain_name_service_and_scores_priority_band_standing_as_strings() -> None:
    push = build_company_push(
        domain="example.com",
        name="Example GmbH",
        service_name="Intelligent Automation",
        priority=73,
        band=AccountScoreBand.HOT,
        standing=AccountScoreStanding.RANKED,
        signal_lines="a line",
        account_url="http://localhost:8080/accounts/1",
    )

    assert push.domain == "example.com"
    assert push.name == "Example GmbH"
    assert push.leadradar_service == "Intelligent Automation"
    assert push.leadradar_priority == "73"
    assert push.leadradar_band == "HOT"
    assert push.leadradar_standing == "RANKED"
    assert isinstance(push.leadradar_priority, str)
    assert isinstance(push.leadradar_band, str)
    assert isinstance(push.leadradar_standing, str)


def test_a_standing_with_no_band_gives_an_empty_band_string() -> None:
    push = build_company_push(
        domain="example.com",
        name="Example GmbH",
        service_name="Intelligent Automation",
        priority=10,
        band=None,
        standing=AccountScoreStanding.BELOW_FIT,
        signal_lines="",
        account_url="http://localhost:8080/accounts/1",
    )

    assert push.leadradar_band == ""
