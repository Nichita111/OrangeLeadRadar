"""Unit tests of [Source detection](/architecture/rules.md#source-detection)'s pure decisions
(`S-ING-05`): which home-page link, if any, becomes a `DETECTED` source of each kind, and the
`SERPAPI` web-search half's query text and domain filter."""

from __future__ import annotations

import pytest

from leadradar.core.enums import AccountSourceKind
from leadradar.core.source_detection import (
    ATS_HOSTS,
    DetectedSource,
    LinkCandidate,
    detect_home_page_sources,
    first_result_on_domain,
    search_query,
)

pytestmark = pytest.mark.unit

DOMAIN = "acme-test.com"


def link(url: str, text: str = "") -> LinkCandidate:
    return LinkCandidate(url=url, text=text)


def test_a_kind_matches_by_path_or_by_text_case_insensitively() -> None:
    by_path = detect_home_page_sources(
        links=[link(f"https://{DOMAIN}/Careers/open-roles")],
        feed_urls=[],
        domain=DOMAIN,
        existing_kinds=frozenset(),
    )
    by_text = detect_home_page_sources(
        links=[link(f"https://{DOMAIN}/join-us", "CAREERS at Acme")],
        feed_urls=[],
        domain=DOMAIN,
        existing_kinds=frozenset(),
    )
    assert [d.kind for d in by_path] == [AccountSourceKind.CAREERS]
    assert [d.kind for d in by_text] == [AccountSourceKind.CAREERS]


def test_a_link_matching_no_term_is_ignored() -> None:
    detected = detect_home_page_sources(
        links=[link(f"https://{DOMAIN}/about", "About us")],
        feed_urls=[],
        domain=DOMAIN,
        existing_kinds=frozenset(),
    )
    assert detected == []


def test_the_first_matching_link_in_document_order_wins_and_at_most_one_per_kind() -> None:
    detected = detect_home_page_sources(
        links=[
            link(f"https://{DOMAIN}/press/first"),
            link(f"https://{DOMAIN}/newsroom/second"),
        ],
        feed_urls=[],
        domain=DOMAIN,
        existing_kinds=frozenset(),
    )
    assert detected == [
        DetectedSource(kind=AccountSourceKind.NEWSROOM, url=f"https://{DOMAIN}/press/first")
    ]


def test_a_subdomain_of_the_registrable_domain_qualifies_but_another_domain_does_not() -> None:
    detected = detect_home_page_sources(
        links=[
            link("https://group.acme-test.com/careers"),
            link("https://other-acme-test.com/careers"),
        ],
        feed_urls=[],
        domain=DOMAIN,
        existing_kinds=frozenset(),
    )
    assert detected == [
        DetectedSource(kind=AccountSourceKind.CAREERS, url="https://group.acme-test.com/careers")
    ]


@pytest.mark.parametrize(
    "url",
    [
        "https://boards.greenhouse.io/acme/jobs/1",
        "https://jobs.lever.co/acme/1",
        "https://acme.myworkdayjobs.com/en-US/acme/job/1",
        "https://jobs.smartrecruiters.com/acme/1",
    ],
)
def test_a_public_ats_host_qualifies_for_careers(url: str) -> None:
    detected = detect_home_page_sources(
        links=[link(url, "Careers")], feed_urls=[], domain=DOMAIN, existing_kinds=frozenset()
    )
    assert detected == [DetectedSource(kind=AccountSourceKind.CAREERS, url=url)]


def test_a_lookalike_ats_host_does_not_qualify() -> None:
    detected = detect_home_page_sources(
        links=[link("https://myworkdayjobs.com.evil-test.com/careers", "Careers")],
        feed_urls=[],
        domain=DOMAIN,
        existing_kinds=frozenset(),
    )
    assert detected == []
    assert "myworkdayjobs.com.evil-test.com" not in ATS_HOSTS


def test_a_kind_in_existing_kinds_is_never_detected() -> None:
    detected = detect_home_page_sources(
        links=[link(f"https://{DOMAIN}/careers")],
        feed_urls=[f"https://{DOMAIN}/feed.xml"],
        domain=DOMAIN,
        existing_kinds=frozenset({AccountSourceKind.CAREERS, AccountSourceKind.RSS_FEED}),
    )
    assert detected == []


def test_rss_feed_takes_the_first_alternate_feed_on_the_account_domain() -> None:
    detected = detect_home_page_sources(
        links=[],
        feed_urls=["https://news.google.com/feed", f"https://{DOMAIN}/feed.xml"],
        domain=DOMAIN,
        existing_kinds=frozenset(),
    )
    assert detected == [
        DetectedSource(kind=AccountSourceKind.RSS_FEED, url=f"https://{DOMAIN}/feed.xml")
    ]


def test_a_feed_only_on_another_domain_is_not_detected() -> None:
    detected = detect_home_page_sources(
        links=[],
        feed_urls=["https://news.google.com/feed", "https://other-acme-test.com/feed.xml"],
        domain=DOMAIN,
        existing_kinds=frozenset(),
    )
    assert detected == []


def test_website_is_never_detected() -> None:
    detected = detect_home_page_sources(
        links=[link(f"https://{DOMAIN}/", "Home")],
        feed_urls=[],
        domain=DOMAIN,
        existing_kinds=frozenset(),
    )
    assert AccountSourceKind.WEBSITE not in {d.kind for d in detected}


def test_search_query_text() -> None:
    assert search_query(AccountSourceKind.CAREERS, "Acme Corp") == '"Acme Corp" careers'
    assert (
        search_query(AccountSourceKind.INVESTOR_RELATIONS, "Acme Corp")
        == '"Acme Corp" investor relations annual report'
    )


def test_first_result_on_domain_skips_off_domain_results() -> None:
    assert (
        first_result_on_domain(
            ["https://other-acme-test.com/x", f"https://{DOMAIN}/careers"], DOMAIN
        )
        == f"https://{DOMAIN}/careers"
    )
    assert first_result_on_domain(["https://other-acme-test.com/x"], DOMAIN) is None
    assert first_result_on_domain([], DOMAIN) is None
