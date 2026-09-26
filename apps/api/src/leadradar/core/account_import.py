"""[`AccountImportRow`](/architecture/interfaces.md#accountimportrow) (`API-22`, `S-ACC-02`):
splitting the uploaded CSV into raw rows and validating one row into its typed fields. Pure
functions over the already-decoded file text; the database lookups the row's outcome also needs
(matching an existing domain, an `ACTIVE` industry, a possible-duplicate name) are the capability
function's job ([Accounts and contacts](/architecture/interfaces.md#accounts-and-contacts))."""

from __future__ import annotations

import csv
import io
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from urllib.parse import urlsplit

from leadradar.core.account_identity import InvalidDomain, normalise_domain
from leadradar.core.enums import AccountOperationalComplexity, AccountSourceKind

#: The CSV columns of [`AccountImportRow`](/architecture/interfaces.md#accountimportrow) that map
#: to an [`account_source`](/architecture/sql-store.md#account_source) row of that kind.
_SOURCE_COLUMNS: dict[str, AccountSourceKind] = {
    "newsroom_url": AccountSourceKind.NEWSROOM,
    "careers_url": AccountSourceKind.CAREERS,
    "investor_relations_url": AccountSourceKind.INVESTOR_RELATIONS,
    "rss_url": AccountSourceKind.RSS_FEED,
}

_ALIAS_SEPARATOR = ";"

# [Source detection](/architecture/rules.md#source-detection): "A feed on `news.google.com` is
# refused: its terms allow personal use only ([ADR-19]
# (/architecture/adrs/adr-19-source-provider-terms-and-limits.md))" — the same refusal applies to
# an `rss_url` column of the import row.
_REFUSED_RSS_HOST = "news.google.com"


class ImportRowOutcome(StrEnum):
    """`ImportResult.rows[].outcome` ([Accounts and contacts]
    (/architecture/interfaces.md#accountimportrow)); an interface-only enum, not a store column,
    so it does not belong in `core.enums`."""

    CREATED = "CREATED"
    UPDATED = "UPDATED"
    POSSIBLE_DUPLICATE = "POSSIBLE_DUPLICATE"
    INVALID = "INVALID"


@dataclass(frozen=True)
class FieldError:
    """One entry of a row's `errors`, in the shape of `details.fields[]`
    ([Conventions](/architecture/interfaces.md#conventions) Envelope)."""

    field: str
    message: str


@dataclass(frozen=True)
class ParsedSource:
    """One [`account_source`](/architecture/sql-store.md#account_source) a row's URL columns
    name."""

    kind: AccountSourceKind
    url: str


@dataclass(frozen=True)
class ParsedImportRow:
    """One [`AccountImportRow`](/architecture/interfaces.md#accountimportrow) after validation.
    `errors` is empty exactly when every other field is usable; an empty CSV cell is `None` (or
    an empty tuple for `aliases`/`sources`), never an error, since only `domain` and `name` are
    required."""

    line: int
    domain: str | None
    name: str | None
    country_code: str | None
    industry: str | None
    employee_count: int | None
    revenue_eur: int | None
    aliases: tuple[str, ...]
    sources: tuple[ParsedSource, ...]
    operational_complexity: AccountOperationalComplexity | None
    linkedin_url: str | None
    notes: str | None
    errors: tuple[FieldError, ...]


def parse_csv_rows(text: str) -> list[dict[str, str]]:
    """Splits the decoded file `text` into its rows, keyed by the header row's column names
    ([`AccountImportRow`](/architecture/interfaces.md#accountimportrow): "UTF-8, comma-separated,
    with this header row")."""
    reader = csv.DictReader(io.StringIO(text))
    return [dict(row) for row in reader]


def _cell(raw: Mapping[str, str | None], column: str) -> str | None:
    value = raw.get(column)
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None


def _optional_int(raw: Mapping[str, str | None], column: str, errors: list[FieldError]) -> int | None:
    text_value = _cell(raw, column)
    if text_value is None:
        return None
    try:
        parsed = int(text_value)
    except ValueError:
        errors.append(FieldError(column, f"{column} must be a whole number."))
        return None
    if parsed < 0:
        errors.append(FieldError(column, f"{column} must not be negative."))
        return None
    return parsed


def parse_import_row(
    line: int, raw: Mapping[str, str | None], active_industry_codes: frozenset[str]
) -> ParsedImportRow:
    """Validates one raw CSV row into a `ParsedImportRow`. `active_industry_codes` is the set of
    `ACTIVE` [`industry`](/architecture/sql-store.md#industry) codes at the time of the request —
    an input, so this stays a pure function of its arguments."""
    errors: list[FieldError] = []

    domain_cell = _cell(raw, "domain")
    domain: str | None = None
    if domain_cell is None:
        errors.append(FieldError("domain", "domain is required."))
    else:
        try:
            domain = normalise_domain(domain_cell)
        except InvalidDomain as exc:
            errors.append(FieldError("domain", str(exc)))

    name = _cell(raw, "name")
    if name is None:
        errors.append(FieldError("name", "name is required."))

    country_code = _cell(raw, "country_code")

    industry = _cell(raw, "industry")
    if industry is not None and industry not in active_industry_codes:
        errors.append(FieldError("industry", f"'{industry}' is not an active industry."))

    employee_count = _optional_int(raw, "employee_count", errors)
    revenue_eur = _optional_int(raw, "revenue_eur", errors)

    aliases_cell = _cell(raw, "aliases") or ""
    aliases = tuple(
        alias.strip() for alias in aliases_cell.split(_ALIAS_SEPARATOR) if alias.strip()
    )

    sources: list[ParsedSource] = []
    for column, kind in _SOURCE_COLUMNS.items():
        url = _cell(raw, column)
        if url is None:
            continue
        if kind == AccountSourceKind.RSS_FEED and urlsplit(url).hostname == _REFUSED_RSS_HOST:
            errors.append(FieldError(column, "a news.google.com feed is refused."))
            continue
        sources.append(ParsedSource(kind=kind, url=url))

    complexity_cell = _cell(raw, "operational_complexity")
    operational_complexity: AccountOperationalComplexity | None = None
    if complexity_cell is not None:
        try:
            operational_complexity = AccountOperationalComplexity(complexity_cell.upper())
        except ValueError:
            errors.append(
                FieldError(
                    "operational_complexity",
                    f"'{complexity_cell}' is not LOW, MEDIUM or HIGH.",
                )
            )

    linkedin_url = _cell(raw, "linkedin_url")
    notes = _cell(raw, "notes")

    return ParsedImportRow(
        line=line,
        domain=domain,
        name=name,
        country_code=country_code,
        industry=industry,
        employee_count=employee_count,
        revenue_eur=revenue_eur,
        aliases=aliases,
        sources=tuple(sources),
        operational_complexity=operational_complexity,
        linkedin_url=linkedin_url,
        notes=notes,
        errors=tuple(errors),
    )
