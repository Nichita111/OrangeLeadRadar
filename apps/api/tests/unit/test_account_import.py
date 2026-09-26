"""Unit tests of [`AccountImportRow`](/architecture/interfaces.md#accountimportrow) parsing:
`core.account_import.parse_csv_rows` and `parse_import_row`."""

from __future__ import annotations

import pytest

from leadradar.core.account_import import (
    FieldError,
    ParsedSource,
    parse_csv_rows,
    parse_import_row,
)
from leadradar.core.enums import AccountOperationalComplexity, AccountSourceKind

pytestmark = pytest.mark.unit

_ACTIVE_INDUSTRIES = frozenset({"LOGISTICS"})


def test_parse_csv_rows_keys_each_row_by_the_header() -> None:
    text = "domain,name\nlufthansagroup.com,Lufthansa Group\n"
    rows = parse_csv_rows(text)
    assert rows == [{"domain": "lufthansagroup.com", "name": "Lufthansa Group"}]


def test_a_row_with_only_domain_and_name_is_valid() -> None:
    row = parse_import_row(2, {"domain": "dhl.com", "name": "DHL Group"}, _ACTIVE_INDUSTRIES)
    assert row.errors == ()
    assert row.domain == "dhl.com"
    assert row.name == "DHL Group"
    assert row.aliases == ()
    assert row.sources == ()


def test_a_row_missing_domain_is_invalid_naming_the_field() -> None:
    row = parse_import_row(3, {"domain": "", "name": "DHL Group"}, _ACTIVE_INDUSTRIES)
    assert row.domain is None
    assert FieldError("domain", "domain is required.") in row.errors


def test_a_row_missing_name_is_invalid_naming_the_field() -> None:
    row = parse_import_row(4, {"domain": "dhl.com", "name": ""}, _ACTIVE_INDUSTRIES)
    assert row.name is None
    assert any(error.field == "name" for error in row.errors)


def test_a_row_with_an_unparseable_domain_is_invalid_naming_the_field() -> None:
    row = parse_import_row(5, {"domain": "not a domain", "name": "X"}, _ACTIVE_INDUSTRIES)
    assert row.domain is None
    assert any(error.field == "domain" for error in row.errors)


def test_an_inactive_or_unknown_industry_is_invalid_naming_the_field() -> None:
    row = parse_import_row(
        6,
        {"domain": "dhl.com", "name": "DHL", "industry": "RETIRED_CODE"},
        _ACTIVE_INDUSTRIES,
    )
    assert any(error.field == "industry" for error in row.errors)


def test_an_active_industry_is_accepted() -> None:
    row = parse_import_row(
        7, {"domain": "dhl.com", "name": "DHL", "industry": "LOGISTICS"}, _ACTIVE_INDUSTRIES
    )
    assert row.industry == "LOGISTICS"
    assert row.errors == ()


@pytest.mark.parametrize("column", ["employee_count", "revenue_eur"])
def test_a_non_numeric_optional_integer_is_invalid_naming_the_field(column: str) -> None:
    row = parse_import_row(
        8, {"domain": "dhl.com", "name": "DHL", column: "not-a-number"}, _ACTIVE_INDUSTRIES
    )
    assert any(error.field == column for error in row.errors)


def test_aliases_are_split_on_semicolon_and_trimmed() -> None:
    row = parse_import_row(
        9,
        {"domain": "dhl.com", "name": "DHL", "aliases": "Deutsche Post DHL ; DHL "},
        _ACTIVE_INDUSTRIES,
    )
    assert row.aliases == ("Deutsche Post DHL", "DHL")


def test_source_columns_map_to_their_kind() -> None:
    row = parse_import_row(
        10,
        {
            "domain": "dhl.com",
            "name": "DHL",
            "newsroom_url": "https://dhl.com/news",
            "careers_url": "https://dhl.com/careers",
            "investor_relations_url": "https://dhl.com/ir",
            "rss_url": "https://dhl.com/feed.xml",
        },
        _ACTIVE_INDUSTRIES,
    )
    assert set(row.sources) == {
        ParsedSource(AccountSourceKind.NEWSROOM, "https://dhl.com/news"),
        ParsedSource(AccountSourceKind.CAREERS, "https://dhl.com/careers"),
        ParsedSource(AccountSourceKind.INVESTOR_RELATIONS, "https://dhl.com/ir"),
        ParsedSource(AccountSourceKind.RSS_FEED, "https://dhl.com/feed.xml"),
    }


def test_a_news_google_com_rss_feed_is_refused() -> None:
    row = parse_import_row(
        11,
        {
            "domain": "dhl.com",
            "name": "DHL",
            "rss_url": "https://news.google.com/rss/search?q=dhl",
        },
        _ACTIVE_INDUSTRIES,
    )
    assert row.sources == ()
    assert any(error.field == "rss_url" for error in row.errors)


def test_operational_complexity_parses_case_insensitively() -> None:
    row = parse_import_row(
        12,
        {"domain": "dhl.com", "name": "DHL", "operational_complexity": "high"},
        _ACTIVE_INDUSTRIES,
    )
    assert row.operational_complexity == AccountOperationalComplexity.HIGH


def test_an_unknown_operational_complexity_is_invalid_naming_the_field() -> None:
    row = parse_import_row(
        13,
        {"domain": "dhl.com", "name": "DHL", "operational_complexity": "EXTREME"},
        _ACTIVE_INDUSTRIES,
    )
    assert any(error.field == "operational_complexity" for error in row.errors)


def test_linkedin_url_and_notes_pass_through() -> None:
    row = parse_import_row(
        14,
        {
            "domain": "dhl.com",
            "name": "DHL",
            "linkedin_url": "https://www.linkedin.com/company/dhl",
            "notes": "A note.",
        },
        _ACTIVE_INDUSTRIES,
    )
    assert row.linkedin_url == "https://www.linkedin.com/company/dhl"
    assert row.notes == "A note."


def test_a_missing_column_is_treated_as_an_empty_cell() -> None:
    row = parse_import_row(15, {"domain": "dhl.com", "name": "DHL"}, _ACTIVE_INDUSTRIES)
    assert row.country_code is None
    assert row.employee_count is None
    assert row.operational_complexity is None
