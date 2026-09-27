"""Unit tests of [Discovery](/architecture/rules.md#discovery) steps 2-4: `news_query`,
`validate_organisation`, `propose`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from leadradar.core.account_identity import normalise_name
from leadradar.core.discovery import (
    Company,
    KnownIdentities,
    OrganisationMention,
    news_query,
    ordering_key,
    propose,
    validate_organisation,
)
from leadradar.core.scoring.settings import (
    Disqualifier,
    DisqualifierKind,
    ICPCriterion,
    ICPCriterionKind,
    ScoringSettings,
    WeightLevel,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 9, 27, 12, 0, tzinfo=UTC)


def _at(days_before: int) -> datetime:
    return _NOW - timedelta(days=days_before)


# The Intelligent Automation ICP of the demo dataset (overview.md), reused so the Fit numbers this
# test checks are the same the rules examples and the demo give.
_ICP_SETTINGS = ScoringSettings(
    icp_criteria=[
        ICPCriterion(
            key="SECTOR",
            kind=ICPCriterionKind.INDUSTRY,
            weight=WeightLevel.HIGH,
            values=["AEROSPACE_AVIATION", "LOGISTICS_TRANSPORT"],
        ),
        ICPCriterion(
            key="REGION",
            kind=ICPCriterionKind.GEOGRAPHY,
            weight=WeightLevel.MEDIUM,
            values=["DE", "AT", "CH", "NL", "BE", "LU", "FR", "IT", "DK", "SE", "NO", "FI"],
        ),
        ICPCriterion(
            key="SIZE", kind=ICPCriterionKind.EMPLOYEE_RANGE, weight=WeightLevel.MEDIUM, min=5000
        ),
        ICPCriterion(
            key="COMPLEXITY",
            kind=ICPCriterionKind.OPERATIONAL_COMPLEXITY,
            weight=WeightLevel.LOW,
            values=["MEDIUM", "HIGH"],
        ),
    ],
    disqualifiers=[
        Disqualifier(
            key="OUTSIDE_EUROPE",
            label="Outside the target region",
            kind=DisqualifierKind.ICP_MISMATCH,
            criterion_key="REGION",
        )
    ],
)

_NO_ONE = KnownIdentities(domains=frozenset(), normalised_names=frozenset())


def _company(
    name: str = "Deutsche Lufthansa AG",
    *,
    country_code: str | None = "DE",
    domain: str | None = None,
    document_id: str = "11111111-1111-1111-1111-111111111111",
    published_at: datetime | None = None,
    quote: str = "Lufthansa announced a cost programme.",
) -> Company:
    return Company(
        name=name,
        normalised_name=normalise_name(name),
        country_code=country_code,
        domain=domain,
        quote=quote,
        document_id=document_id,
        published_at=published_at,
    )


# ── news_query ──────────────────────────────────────────────────────────────────


def test_news_query_joins_hint_terms() -> None:
    assert news_query(["automation", "RPA"]) == '"automation" OR "RPA"'


def test_news_query_with_no_hint_terms_is_empty() -> None:
    assert news_query([]) == ""


# ── validate_organisation (G3) ───────────────────────────────────────────────────


def _mention(
    *,
    name: str = "Deutsche Lufthansa AG",
    country_code: str | None = None,
    website: str | None = None,
    quote: str = "Lufthansa announced a cost programme.",
) -> OrganisationMention:
    return OrganisationMention(
        name=name,
        country_code=country_code,
        website=website,
        quote=quote,
        document_id="11111111-1111-1111-1111-111111111111",
        published_at=None,
    )


_TEXT = "Lufthansa announced a cost programme. It is based at www.lufthansa.com in Germany."


def test_organisation_kept_with_a_stated_website() -> None:
    company = validate_organisation(_mention(website="www.lufthansa.com"), _TEXT)
    assert company is not None
    assert company.domain == "lufthansa.com"


def test_organisation_kept_with_only_a_stated_country_and_null_domain() -> None:
    company = validate_organisation(_mention(country_code="DE"), _TEXT)
    assert company is not None
    assert company.domain is None
    assert company.country_code == "DE"


def test_organisation_dropped_when_quote_is_not_in_the_text() -> None:
    mention = _mention(country_code="DE", quote="Not in the document at all.")
    assert validate_organisation(mention, _TEXT) is None


def test_organisation_dropped_with_neither_website_nor_country() -> None:
    assert validate_organisation(_mention(), _TEXT) is None


def test_website_absent_from_the_text_counts_as_unstated() -> None:
    mention = _mention(website="www.other-domain.com")
    assert validate_organisation(mention, _TEXT) is None


def test_website_with_no_registrable_domain_counts_as_unstated() -> None:
    text = f"{_TEXT} See not-a-domain for more."
    mention = _mention(website="not-a-domain")
    assert validate_organisation(mention, text) is None


def test_non_iso_country_counts_as_unstated() -> None:
    mention = _mention(country_code="ZZ")
    assert validate_organisation(mention, _TEXT) is None


def test_name_that_normalises_to_empty_is_dropped() -> None:
    mention = _mention(name="AG", country_code="DE")
    assert validate_organisation(mention, _TEXT) is None


# ── propose: identity drops (Discovery step 3, Account identity) ────────────────


def test_a_company_whose_domain_equals_an_account_domain_is_dropped() -> None:
    accounts = KnownIdentities(domains=frozenset({"lufthansa.com"}), normalised_names=frozenset())
    result = propose(
        [_company(domain="lufthansa.com", country_code=None)],
        accounts=accounts,
        earlier_candidates=_NO_ONE,
        settings=_ICP_SETTINGS,
        max_candidates=50,
        now=_NOW,
    )
    assert result == []


def test_a_company_whose_normalised_name_equals_an_account_alias_is_dropped() -> None:
    accounts = KnownIdentities(
        domains=frozenset(), normalised_names=frozenset({"deutsche lufthansa"})
    )
    result = propose(
        [_company(name="Deutsche Lufthansa AG")],
        accounts=accounts,
        earlier_candidates=_NO_ONE,
        settings=_ICP_SETTINGS,
        max_candidates=50,
        now=_NOW,
    )
    assert result == []


@pytest.mark.parametrize("status_domain_match", [True, False])
def test_a_company_matching_an_earlier_candidate_is_dropped_whatever_its_status(
    status_domain_match: bool,
) -> None:
    # `status` is not modelled here: `propose` reads earlier candidates of any status alike, so
    # the caller passing them in is what the "any status" rule tests: the identity set carries no
    # status field at all.
    earlier = KnownIdentities(
        domains=frozenset({"lufthansa.com"}) if status_domain_match else frozenset(),
        normalised_names=frozenset() if status_domain_match else frozenset({"deutsche lufthansa"}),
    )
    result = propose(
        [_company(domain="lufthansa.com" if status_domain_match else None)],
        accounts=_NO_ONE,
        earlier_candidates=earlier,
        settings=_ICP_SETTINGS,
        max_candidates=50,
        now=_NOW,
    )
    assert result == []


# ── propose: disqualification (Discovery step 3) ─────────────────────────────────


def test_a_known_country_outside_region_is_dropped_under_icp_mismatch() -> None:
    result = propose(
        [_company(country_code="US")],
        accounts=_NO_ONE,
        earlier_candidates=_NO_ONE,
        settings=_ICP_SETTINGS,
        max_candidates=50,
        now=_NOW,
    )
    assert result == []


def test_an_unknown_country_is_kept_despite_the_region_disqualifier() -> None:
    result = propose(
        [_company(country_code=None)],
        accounts=_NO_ONE,
        earlier_candidates=_NO_ONE,
        settings=_ICP_SETTINGS,
        max_candidates=50,
        now=_NOW,
    )
    assert len(result) == 1


def test_a_signal_disqualifier_never_drops_a_candidate() -> None:
    settings = _ICP_SETTINGS.model_copy(
        update={
            "disqualifiers": [
                Disqualifier(
                    key="INSOLVENT",
                    label="In insolvency",
                    kind=DisqualifierKind.SIGNAL,
                    question_key="INSOLVENCY",
                    min_strength="MEDIUM",
                )
            ]
        }
    )
    result = propose(
        [_company(country_code="DE")],
        accounts=_NO_ONE,
        earlier_candidates=_NO_ONE,
        settings=settings,
        max_candidates=50,
        now=_NOW,
    )
    assert len(result) == 1


# ── propose: Fit examples (Fit score) ────────────────────────────────────────────


def test_fit_estimate_with_known_country_and_rest_unknown_is_63() -> None:
    result = propose(
        [_company(country_code="DE")],
        accounts=_NO_ONE,
        earlier_candidates=_NO_ONE,
        settings=_ICP_SETTINGS,
        max_candidates=50,
        now=_NOW,
    )
    assert result[0].fit_estimate == 63


def test_fit_estimate_with_unknown_country_is_50() -> None:
    result = propose(
        [_company(country_code=None)],
        accounts=_NO_ONE,
        earlier_candidates=_NO_ONE,
        settings=_ICP_SETTINGS,
        max_candidates=50,
        now=_NOW,
    )
    assert result[0].fit_estimate == 50


def test_fit_estimate_with_no_criteria_is_100() -> None:
    result = propose(
        [_company(country_code="US")],
        accounts=_NO_ONE,
        earlier_candidates=_NO_ONE,
        settings=ScoringSettings(),
        max_candidates=50,
        now=_NOW,
    )
    assert result[0].fit_estimate == 100


# ── propose: merge (G4, G12) ──────────────────────────────────────────────────────


def test_two_mentions_of_one_company_merge_keeping_the_newer_article() -> None:
    older = _company(document_id="1" * 32, published_at=_at(10), quote="older quote")
    newer = _company(document_id="2" * 32, published_at=_at(1), quote="newer quote")
    result = propose(
        [older, newer],
        accounts=_NO_ONE,
        earlier_candidates=_NO_ONE,
        settings=ScoringSettings(),
        max_candidates=50,
        now=_NOW,
    )
    assert len(result) == 1
    assert result[0].quote == "newer quote"


def test_merge_at_equal_published_at_keeps_the_one_first_in_search_order() -> None:
    same_date = _at(5)
    first = _company(document_id="1" * 32, published_at=same_date, quote="first")
    second = _company(document_id="2" * 32, published_at=same_date, quote="second")
    result = propose(
        [first, second],
        accounts=_NO_ONE,
        earlier_candidates=_NO_ONE,
        settings=ScoringSettings(),
        max_candidates=50,
        now=_NOW,
    )
    assert result[0].quote == "first"


# ── propose: ranking and cap (Discovery step 4, G12) ─────────────────────────────


@pytest.mark.parametrize("count", [4, 5, 6])
def test_ranking_keeps_exactly_max_candidates_at_the_cap(count: int) -> None:
    companies = [
        _company(name=f"Company {i}", document_id=f"{i:032x}", country_code="DE")
        for i in range(count)
    ]
    result = propose(
        companies,
        accounts=_NO_ONE,
        earlier_candidates=_NO_ONE,
        settings=ScoringSettings(),
        max_candidates=5,
        now=_NOW,
    )
    assert len(result) == min(count, 5)


def test_equal_fit_ranks_the_newer_article_first() -> None:
    older = _company(name="Alpha", document_id="1" * 32, published_at=_at(10))
    newer = _company(name="Beta", document_id="2" * 32, published_at=_at(1))
    result = propose(
        [older, newer],
        accounts=_NO_ONE,
        earlier_candidates=_NO_ONE,
        settings=ScoringSettings(),
        max_candidates=1,
        now=_NOW,
    )
    assert len(result) == 1
    assert result[0].name == "Beta"


def test_equal_fit_and_published_at_ranks_the_smaller_normalised_name_first() -> None:
    same_date = _at(1)
    beta = _company(name="Beta Corp", document_id="1" * 32, published_at=same_date)
    alpha = _company(name="Alpha Corp", document_id="2" * 32, published_at=same_date)
    result = propose(
        [beta, alpha],
        accounts=_NO_ONE,
        earlier_candidates=_NO_ONE,
        settings=ScoringSettings(),
        max_candidates=2,
        now=_NOW,
    )
    assert [item.name for item in result] == ["Alpha Corp", "Beta Corp"]


def test_a_null_published_at_ranks_after_any_known_one() -> None:
    known = _company(name="Known Co", document_id="1" * 32, published_at=_at(400))
    unknown = _company(name="Unknown Co", document_id="2" * 32, published_at=None)
    result = propose(
        [unknown, known],
        accounts=_NO_ONE,
        earlier_candidates=_NO_ONE,
        settings=ScoringSettings(),
        max_candidates=2,
        now=_NOW,
    )
    assert [item.name for item in result] == ["Known Co", "Unknown Co"]


def test_ordering_key_orders_by_fit_desc_then_published_desc_nulls_last_then_name() -> None:
    high_new = ordering_key(80, _at(1), "b")
    high_old = ordering_key(80, _at(10), "a")
    high_unknown = ordering_key(80, None, "a")
    low = ordering_key(50, _at(1), "a")
    assert sorted([low, high_unknown, high_old, high_new]) == [
        high_new,
        high_old,
        high_unknown,
        low,
    ]
