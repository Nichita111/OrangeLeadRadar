"""Typed errors of the [feedback and alerts](/architecture/interfaces.md#feedback-and-alerts)
capability, mapped once at the edge (`api/errors.py`) onto `404 NOT_FOUND`."""

from __future__ import annotations


class FeedbackError(Exception):
    """Base of every typed error this capability raises."""


class ScoreNotFound(FeedbackError):
    """No current [`account_score`](/architecture/sql-store.md#account_score) for the account
    and service — the account, the service, or a current score for the pair does not exist
    (`API-46`, D2 of [Feedback and alerts](/architecture/interfaces.md#feedback-and-alerts))."""


class FindingNotFound(FeedbackError):
    """No [`finding`](/architecture/sql-store.md#finding) row for the given id (`API-47`)."""
