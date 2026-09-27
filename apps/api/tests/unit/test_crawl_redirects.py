"""Unit tests of redirect following ([Fetch window](/architecture/rules.md#fetch-window) step 3;
`adr-21-source-detection-timing-and-crawler-redirects.md` G8, G10)."""

from __future__ import annotations

import pytest

from leadradar.core.crawl_redirects import redirect_target

pytestmark = pytest.mark.unit

DOMAIN = "dhl.com"
REQUEST_URL = f"https://{DOMAIN}/"


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_each_redirect_status_with_a_relative_location_gives_the_absolute_target(
    status: int,
) -> None:
    assert redirect_target(REQUEST_URL, status, "/en/home", DOMAIN) == f"https://{DOMAIN}/en/home"


@pytest.mark.parametrize("status", [301, 302, 303, 307, 308])
def test_each_redirect_status_with_an_absolute_location_gives_it(status: int) -> None:
    target = "https://www.dhl.com/en/home"
    assert redirect_target(REQUEST_URL, status, target, DOMAIN) == target


def test_a_subdomain_of_the_account_domain_qualifies() -> None:
    assert redirect_target(REQUEST_URL, 301, "https://www.dhl.com/", DOMAIN) == "https://www.dhl.com/"


def test_an_off_domain_target_gives_none() -> None:
    assert redirect_target(REQUEST_URL, 301, "https://evil.example/", DOMAIN) is None


def test_a_missing_location_gives_none() -> None:
    assert redirect_target(REQUEST_URL, 301, None, DOMAIN) is None


@pytest.mark.parametrize("status", [300, 304])
def test_a_non_redirect_status_gives_none(status: int) -> None:
    assert redirect_target(REQUEST_URL, status, "/en/home", DOMAIN) is None
