"""[Priority, standing and band](/architecture/rules.md#priority-standing-and-band).

`priority_standing_band(...)`.

Pure function; no I/O.
"""

from __future__ import annotations

from leadradar.core.enums import AccountScoreBand, AccountScoreStanding
from leadradar.core.scoring.disqualification import DisqEntry


def priority_standing_band(
    fit: int,
    intent: int,
    disq_entries: list[DisqEntry],
    lead_feedback_verdict: str | None,
    fit_weight: float,
    intent_weight: float,
    min_fit: int,
    hot_threshold: int,
    warm_threshold: int,
) -> tuple[int, AccountScoreStanding, AccountScoreBand | None]:
    """Compute Priority, Standing and Band.

    Returns (priority, standing, band). Band is None for non-RANKED accounts.

    Standing precedence: CUSTOMER > DISQUALIFIED > BELOW_FIT > RANKED.
    """
    raw_priority = fit_weight * fit + intent_weight * intent
    priority = int(raw_priority + 0.5)

    # Standing: first match wins
    if lead_feedback_verdict == "ALREADY_CUSTOMER":
        standing = AccountScoreStanding.CUSTOMER
    elif any(e.matched and not e.overridden for e in disq_entries):
        standing = AccountScoreStanding.DISQUALIFIED
    elif fit < min_fit:
        standing = AccountScoreStanding.BELOW_FIT
    else:
        standing = AccountScoreStanding.RANKED

    # Band: only for RANKED
    if standing == AccountScoreStanding.RANKED:
        if priority >= hot_threshold:
            band: AccountScoreBand | None = AccountScoreBand.HOT
        elif priority >= warm_threshold:
            band = AccountScoreBand.WARM
        else:
            band = AccountScoreBand.COLD
    else:
        band = None

    return (priority, standing, band)
