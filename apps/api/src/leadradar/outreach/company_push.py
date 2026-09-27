"""[`CompanyPush`](/architecture/interfaces.md#companypush): the pure selection of an account's
top signals and the frozen shape [`API-70`](/architecture/interfaces.md#crm) sends. No I/O, no
clock: `outreach.queries` reads the account, service, score and finding rows this module needs.

`top_finding_ids` is the one selection [`ProspectRow`](/architecture/interfaces.md#prospectrow)
`top_signals` must reuse, not copy, as the [`CompanyPush`](/architecture/interfaces.md#companypush)
`leadradar_top_signals` row states."""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime

from leadradar.core.enums import AccountScoreBand, AccountScoreStanding, SignalQuestionPolarity


@dataclass(frozen=True)
class TopSignalText:
    """One selected finding's evidence, in the order `top_finding_ids` chose it."""

    question_text: str
    quote: str


@dataclass(frozen=True)
class CompanyPush:
    """[`CompanyPush`](/architecture/interfaces.md#companypush), the request
    [`API-70`](/architecture/interfaces.md#crm) sends."""

    domain: str
    name: str
    leadradar_service: str
    leadradar_priority: str
    leadradar_band: str
    leadradar_standing: str
    leadradar_top_signals: str
    leadradar_url: str


def intent_question_entries(breakdown: Mapping[str, object]) -> list[object]:
    """The raw `intent.questions[]` entries of the
    [Score breakdown](/architecture/rules.md#score-breakdown), or `[]` when `breakdown` holds no
    such list. The one walk of the breakdown's question entries; callers filter and read them."""
    intent = breakdown.get("intent")
    questions = intent.get("questions") if isinstance(intent, dict) else None
    return questions if isinstance(questions, list) else []


def top_finding_ids(
    breakdown: Mapping[str, object],
    observed_at_by_finding: Mapping[str, datetime],
    limit: int,
) -> list[str]:
    """The positive `intent.questions[]` entries of the
    [Score breakdown](/architecture/rules.md#score-breakdown), most `points` first, then
    `observed_at` descending, as [`CompanyPush`](/architecture/interfaces.md#companypush)
    `leadradar_top_signals` states, at most `limit` of them."""
    candidates: list[tuple[str, float, datetime]] = []
    for entry in intent_question_entries(breakdown):
        if not isinstance(entry, dict) or entry.get("polarity") != SignalQuestionPolarity.POSITIVE:
            continue
        finding_id = entry.get("finding_id")
        if not isinstance(finding_id, str):
            continue
        points = float(entry["points"])
        candidates.append((finding_id, points, observed_at_by_finding[finding_id]))
    candidates.sort(key=lambda candidate: (-candidate[1], -candidate[2].timestamp()))
    return [finding_id for finding_id, _, _ in candidates[:limit]]


def top_signal_lines(signals: Sequence[TopSignalText]) -> str:
    """One `question text — "quote"` line per signal, in the given order, joined by a newline;
    the empty string when `signals` is empty, as
    [`CompanyPush`](/architecture/interfaces.md#companypush) states."""
    return "\n".join(f'{signal.question_text} — "{signal.quote}"' for signal in signals)


def account_detail_url(app_base_url: str, account_id: uuid.UUID) -> str:
    """`APP_BASE_URL` joined to the
    [Account detail](/features/prospect-dashboard.md#account-detail) route, with no double
    slash."""
    return f"{app_base_url.rstrip('/')}/accounts/{account_id}"


def build_company_push(
    *,
    domain: str,
    name: str,
    service_name: str,
    priority: int,
    band: AccountScoreBand | None,
    standing: AccountScoreStanding,
    signal_lines: str,
    account_url: str,
) -> CompanyPush:
    """Assembles [`CompanyPush`](/architecture/interfaces.md#companypush) from the current
    [`account_score`](/architecture/sql-store.md#account_score); Priority, band and standing are
    carried as strings. `band` is `None` unless `standing` is `RANKED`."""
    return CompanyPush(
        domain=domain,
        name=name,
        leadradar_service=service_name,
        leadradar_priority=str(priority),
        leadradar_band=band.value if band is not None else "",
        leadradar_standing=standing.value,
        leadradar_top_signals=signal_lines,
        leadradar_url=account_url,
    )
