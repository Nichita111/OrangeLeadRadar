"""[Alerts](/architecture/rules.md#alerts): `alerts(...)`.

Pure function; no I/O.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime

from leadradar.core.enums import AccountScoreBand, AccountScoreStanding, AlertKind


@dataclass(frozen=True)
class AlertToCreate:
    """One alert to insert into the `alert` table."""

    account_id: str
    service_id: str
    kind: AlertKind
    finding_id: str | None  # for STRONG_SIGNAL
    score_id: str | None  # filled by the caller after score row insert


# Band rank for comparison: None=0, COLD=1, WARM=2, HOT=3
_BAND_RANK: dict[AccountScoreBand | None, int] = {
    None: 0,
    AccountScoreBand.COLD: 1,
    AccountScoreBand.WARM: 2,
    AccountScoreBand.HOT: 3,
}


def alerts(
    new_score_id: str | None,
    new_standing: AccountScoreStanding,
    new_band: AccountScoreBand | None,
    previous_band: AccountScoreBand | None,
    new_findings: list[dict[str, object]],
    active_settings: Mapping[str, object],
    alert_max_age_days: int,
    as_of: datetime,
    account_id: str,
    service_id: str,
) -> list[AlertToCreate]:
    """Compute the alerts to create after inserting a new score.

    `new_findings` is a list of finding dicts with: id, question_key, strength, observed_at
    (datetime). For a RESCORE triggered by activation these are empty; for a refresh they are
    the findings created by the same run.

    `active_settings` is the raw scoring settings dict (keys: questions, weight_values).
    """
    result: list[AlertToCreate] = []

    # BAND_UP
    new_rank = _BAND_RANK.get(new_band, 0)
    prev_rank = _BAND_RANK.get(previous_band, 0)
    if new_rank > prev_rank and new_rank >= 2:
        result.append(
            AlertToCreate(
                account_id=account_id,
                service_id=service_id,
                kind=AlertKind.BAND_UP,
                finding_id=None,
                score_id=new_score_id,
            )
        )

    # STRONG_SIGNAL
    if new_standing == AccountScoreStanding.RANKED:
        # Build a lookup: question_key → (weight, polarity) from the active settings
        raw_questions = active_settings.get("questions", [])
        questions_list: list[object] = (
            list(raw_questions) if isinstance(raw_questions, list) else []
        )
        q_info: dict[str, dict[str, str]] = {}
        for qs in questions_list:
            if isinstance(qs, dict):
                qk = str(qs.get("question_key", ""))
                q_info[qk] = {
                    "weight": str(qs.get("weight", "LOW")),
                    "polarity": str(qs.get("polarity", "POSITIVE")),
                }

        for f in new_findings:
            if str(f.get("strength", "")) != "STRONG":
                continue
            q_key = str(f.get("question_key", ""))
            info = q_info.get(q_key)
            if info is None:
                continue
            if info["polarity"] != "POSITIVE":
                continue
            if info["weight"] != "HIGH":
                continue
            observed_at = f.get("observed_at")
            if not isinstance(observed_at, datetime):
                continue
            age_days = max(0.0, (as_of - observed_at).total_seconds() / 86400.0)
            if age_days > alert_max_age_days:
                continue
            result.append(
                AlertToCreate(
                    account_id=account_id,
                    service_id=service_id,
                    kind=AlertKind.STRONG_SIGNAL,
                    finding_id=str(f["id"]) if f.get("id") is not None else None,
                    score_id=new_score_id,
                )
            )

    return result
