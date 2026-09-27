"""Unit tests of the `WEBSITE` plug-in's pure home-page parsing ([Source detection]
(/architecture/rules.md#source-detection) Algorithm, order 9c of
`.work/source-detection-enrichment/design.md`)."""

from __future__ import annotations

import pytest

from leadradar.core.source_detection import LinkCandidate
from leadradar.plugins.website import home_page_candidates

pytestmark = pytest.mark.unit

BASE_URL = "https://acme-test.com/"


def test_links_resolve_against_the_base_url_drop_fragments_and_keep_text_and_order() -> None:
    body = (
        "<html><body>"
        '<a href="/careers#top">Careers</a>'
        '<a href="https://acme-test.com/news">  News  </a>'
        "</body></html>"
    )

    links, feed_urls = home_page_candidates(body, BASE_URL)

    assert links == [
        LinkCandidate(url="https://acme-test.com/careers", text="Careers"),
        LinkCandidate(url="https://acme-test.com/news", text="News"),
    ]
    assert feed_urls == []


def test_only_rss_and_atom_alternate_links_are_kept_and_resolved() -> None:
    body = (
        "<html><head>"
        '<link rel="alternate" type="application/rss+xml" href="/feed.xml">'
        '<link rel="alternate" type="application/atom+xml" href="https://acme-test.com/atom.xml">'
        '<link rel="alternate" type="application/json" href="/feed.json">'
        '<link rel="stylesheet" type="application/rss+xml" href="/not-a-feed.xml">'
        "</head><body></body></html>"
    )

    _, feed_urls = home_page_candidates(body, BASE_URL)

    assert feed_urls == ["https://acme-test.com/feed.xml", "https://acme-test.com/atom.xml"]


def test_a_link_with_no_href_is_ignored() -> None:
    body = "<html><body><a>No href</a></body></html>"

    links, feed_urls = home_page_candidates(body, BASE_URL)

    assert links == []
    assert feed_urls == []
