"""[Triage](/architecture/rules.md#triage): pure function that maps classifier answers to a
triage outcome and the services kept.

No I/O; the caller calls the classifier and passes its answers in.
"""

from __future__ import annotations

from dataclasses import dataclass

from leadradar.core.enums import DocumentTriageOutcome, SourcePluginCode

# Sources that are about the account by construction — ABOUT_ACCOUNT is skipped.
_OWN_SOURCES: frozenset[str] = frozenset(
    {
        SourcePluginCode.CAREERS,
        SourcePluginCode.CRUNCHBASE,
        # Any source whose kind is the account's own website/newsroom/IR/RSS is treated as
        # own-source by the caller setting `is_own_source=True`.
    }
)

ABOUT_ACCOUNT_QUESTION_ID = "ABOUT_ACCOUNT"
RELEVANT_QUESTION_PREFIX = "RELEVANT_"


@dataclass(frozen=True)
class TriageResult:
    """Outcome of the Triage rule for one document."""

    outcome: DocumentTriageOutcome
    # Service ids kept (non-empty only for KEPT)
    kept_service_ids: frozenset[str]
    # Raw probability that the document is about its account; None when skipped.
    about_account_p: float | None


def triage(
    *,
    is_own_source: bool,
    service_ids: list[str],
    answers: dict[str, dict[str, float]],
    triage_about_min_p: float,
    triage_relevance_min_p: float,
) -> TriageResult:
    """Apply [Triage](/architecture/rules.md#triage) to one document's classifier answers.

    Parameters
    ----------
    is_own_source:
        True when the document came from the account's own source (WEBSITE, NEWSROOM,
        INVESTOR_RELATIONS, RSS_FEED) or from CAREERS or CRUNCHBASE — the ABOUT_ACCOUNT
        question is skipped for those.
    service_ids:
        Active service ids that were included in the classifier request.
    answers:
        Mapping from question id to ``{answer_key: probability}`` as returned by the
        classifier.  Question ids are ``ABOUT_ACCOUNT`` and ``RELEVANT_{service_id}``.
    triage_about_min_p:
        ``TRIAGE_ABOUT_MIN_P`` from the worker runtime.
    triage_relevance_min_p:
        ``TRIAGE_RELEVANCE_MIN_P`` from the worker runtime.
    """
    # Step 1 — NOT_ABOUT_ACCOUNT check
    about_account_p: float | None = None
    if not is_own_source:
        about_probs = answers.get(ABOUT_ACCOUNT_QUESTION_ID)
        if about_probs is not None:
            about_account_p = about_probs.get("YES", 0.0)
            if about_account_p < triage_about_min_p:
                return TriageResult(
                    outcome=DocumentTriageOutcome.NOT_ABOUT_ACCOUNT,
                    kept_service_ids=frozenset(),
                    about_account_p=about_account_p,
                )

    # Step 2 — relevance per service
    kept: set[str] = set()
    for svc_id in service_ids:
        q_id = f"{RELEVANT_QUESTION_PREFIX}{svc_id}"
        rel_probs = answers.get(q_id, {})
        relevance_p = rel_probs.get("YES", 0.0)
        if relevance_p >= triage_relevance_min_p:
            kept.add(svc_id)

    if not kept:
        return TriageResult(
            outcome=DocumentTriageOutcome.IRRELEVANT,
            kept_service_ids=frozenset(),
            about_account_p=about_account_p,
        )

    return TriageResult(
        outcome=DocumentTriageOutcome.KEPT,
        kept_service_ids=frozenset(kept),
        about_account_p=about_account_p,
    )
