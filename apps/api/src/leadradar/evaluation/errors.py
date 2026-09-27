"""Typed errors of the evaluation capability, mapped once at the edge (`api/errors.py`) onto the
envelope of [Conventions](/architecture/interfaces.md#conventions)."""

from __future__ import annotations


class EvaluationError(Exception):
    """Base of every typed error this capability raises."""


class ServiceNotFound(EvaluationError):
    """`API-50`: `service_id` names no [`service`](/architecture/sql-store.md#service)
    (`404 NOT_FOUND`)."""


class ChunkNotFound(EvaluationError):
    """`API-51`: `chunk_id` names no [`chunk`](/architecture/sql-store.md#chunk)
    (`404 NOT_FOUND`)."""


class QuestionNotFound(EvaluationError):
    """`API-51`: `question_id` names no [`signal_question`]
    (/architecture/sql-store.md#signal_question) (`404 NOT_FOUND`)."""


class RevisionNotCurrent(EvaluationError):
    """`API-51`: `question_revision` is not the question's current `revision`
    (`409 CONFLICT`)."""


class ResultNotFound(EvaluationError):
    """`API-55`: no [`evaluation_result`](/architecture/sql-store.md#evaluation_result) for
    `run_id` (`404 NOT_FOUND`)."""
