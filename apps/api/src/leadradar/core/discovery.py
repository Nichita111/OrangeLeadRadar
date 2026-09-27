"""[Discovery](/architecture/rules.md#discovery) steps 2-4: the news query, the validation of one
extracted organisation (G3), and the merge, drop, score and rank of the companies a run's
documents named (G4, G12). Pure functions of their inputs; no I/O, no clock of its own — the
caller passes `now` for [Disqualification](/architecture/rules.md#disqualification)'s decay,
which never applies here since a candidate carries no finding."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime

from leadradar.core.account_identity import InvalidDomain, normalise_domain, normalise_name
from leadradar.core.countries import ISO_3166_1_ALPHA_2
from leadradar.core.fetch_window import terms_clause
from leadradar.core.scoring.disqualification import disqualify
from leadradar.core.scoring.fit import augment_icp_match, fit
from leadradar.core.scoring.settings import DisqualifierKind, ScoringSettings

_EPOCH = datetime.min.replace(tzinfo=UTC)


def news_query(hint_terms: Sequence[str]) -> str:
    """[Discovery](/architecture/rules.md#discovery) step 2: the query made of the `hint_terms`
    of the service's active positive questions whose `source_types` include `NEWS`. The empty
    string, with no such terms, searches no news (the caller skips the plug-in)."""
    return terms_clause(hint_terms)


@dataclass(frozen=True)
class OrganisationMention:
    """One [`Organisation`](/architecture/interfaces.md#organisation) the LLM named for one kept
    document, before G3's validation."""

    name: str
    country_code: str | None
    website: str | None
    quote: str
    document_id: str
    published_at: datetime | None


@dataclass(frozen=True)
class Company:
    """A validated organisation mention: [Discovery](/architecture/rules.md#discovery) step 2's
    output, and step 3's input."""

    name: str
    normalised_name: str
    country_code: str | None
    domain: str | None
    quote: str
    document_id: str
    published_at: datetime | None


def validate_organisation(mention: OrganisationMention, text: str) -> Company | None:
    """[Discovery](/architecture/rules.md#discovery) step 2, G3: `None` unless `mention.quote` is
    a substring of `text`, `mention.name` normalises to something, and the organisation has a
    stated website — in `text`, with a registrable domain, which becomes the candidate's
    `domain` — or a stated country, an ISO 3166-1 alpha-2 code. An invalid website or country is
    unstated rather than rejecting the mention outright."""
    if mention.quote not in text:
        return None
    normalised_name = normalise_name(mention.name)
    if not normalised_name:
        return None

    domain: str | None = None
    if mention.website is not None and mention.website in text:
        try:
            domain = normalise_domain(mention.website)
        except InvalidDomain:
            domain = None

    country_code = mention.country_code if mention.country_code in ISO_3166_1_ALPHA_2 else None

    if domain is None and country_code is None:
        return None

    return Company(
        name=mention.name,
        normalised_name=normalised_name,
        country_code=country_code,
        domain=domain,
        quote=mention.quote,
        document_id=mention.document_id,
        published_at=mention.published_at,
    )


@dataclass(frozen=True)
class KnownIdentities:
    """Domains and normalised names a proposed company must not match ([Account identity]
    (/architecture/rules.md#account-identity)): an account's domain and every one of its
    aliases' normalised names, or an earlier candidate's domain and its own normalised name, of
    any status."""

    domains: frozenset[str]
    normalised_names: frozenset[str]


def _matches(company: Company, known: KnownIdentities) -> bool:
    return (
        company.domain is not None and company.domain in known.domains
    ) or company.normalised_name in known.normalised_names


def _mention_rank(published_at: datetime | None) -> tuple[int, datetime]:
    """Higher for the newer article; an unknown `published_at` never outranks a known one."""
    return (0, _EPOCH) if published_at is None else (1, published_at)


def _merge_mentions(companies: Sequence[Company]) -> list[Company]:
    """[Discovery](/architecture/rules.md#discovery) step 3, G4: one company per normalised name,
    carrying the mention of the newest article naming it; at equal `published_at` — including two
    unknown ones — the mention first in `companies`' search order wins."""
    kept: dict[str, Company] = {}
    for mention in companies:
        key = mention.normalised_name
        current = kept.get(key)
        if current is None or _mention_rank(mention.published_at) > _mention_rank(
            current.published_at
        ):
            kept[key] = mention
    return list(kept.values())


@dataclass(frozen=True)
class Proposal:
    """One company [Discovery](/architecture/rules.md#discovery) step 4 proposes as a
    `discovery_candidate`."""

    name: str
    normalised_name: str
    country_code: str | None
    domain: str | None
    quote: str
    document_id: str
    published_at: datetime | None
    fit_estimate: int


def ordering_key(
    fit_estimate: int, published_at: datetime | None, normalised_name: str
) -> tuple[int, int, float, str]:
    """The one ordering both `propose`'s ranking and `API-30`'s SQL order use (G12): `fit_estimate`
    descending, then the naming article's `published_at` newest first with an unknown one last,
    then `normalised_name` ascending."""
    published_known = 0 if published_at is not None else 1
    published_value = -published_at.timestamp() if published_at is not None else 0.0
    return (-fit_estimate, published_known, published_value, normalised_name)


def propose(
    companies: Sequence[Company],
    *,
    accounts: KnownIdentities,
    earlier_candidates: KnownIdentities,
    settings: ScoringSettings,
    max_candidates: int,
    now: datetime,
) -> list[Proposal]:
    """[Discovery](/architecture/rules.md#discovery) steps 3-4: merges mentions of one company
    (G4), drops a match of an existing account or an earlier candidate of any status, drops one an
    `ICP_MISMATCH` disqualifier excludes on its known attributes, computes `fit_estimate` over
    those attributes, and keeps the `max_candidates` best by the one ordering key (G12)."""
    icp_criteria = [criterion.model_dump() for criterion in settings.icp_criteria]
    disqualifiers = [d.model_dump() for d in settings.disqualifiers]

    proposals: list[Proposal] = []
    for company in _merge_mentions(companies):
        if _matches(company, accounts) or _matches(company, earlier_candidates):
            continue

        attributes: dict[str, object] = {
            "country_code": company.country_code,
            "industry": None,
            "employee_count": None,
            "revenue_eur": None,
            "operational_complexity": None,
        }
        fit_result = fit(
            attributes=attributes,
            icp_criteria=icp_criteria,
            weight_values=settings.weight_values,
            unknown_match=settings.unknown_match,
        )
        augmented = augment_icp_match(attributes, fit_result.criteria)
        disq_entries = disqualify(
            disqualifiers=disqualifiers,
            attributes=augmented,
            findings=[],
            active_overrides=[],
            min_decay=settings.min_decay,
            strength_values=settings.strength_values,
            default_half_life_days=settings.default_half_life_days,
            as_of=now,
        )
        if any(
            entry.kind == DisqualifierKind.ICP_MISMATCH and entry.matched and not entry.overridden
            for entry in disq_entries
        ):
            continue

        proposals.append(
            Proposal(
                name=company.name,
                normalised_name=company.normalised_name,
                country_code=company.country_code,
                domain=company.domain,
                quote=company.quote,
                document_id=company.document_id,
                published_at=company.published_at,
                fit_estimate=fit_result.value,
            )
        )

    proposals.sort(key=lambda p: ordering_key(p.fit_estimate, p.published_at, p.normalised_name))
    return proposals[:max_candidates]
