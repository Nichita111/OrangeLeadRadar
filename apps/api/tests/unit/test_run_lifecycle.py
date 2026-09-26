"""Unit tests of [Run lifecycle](/architecture/services/worker.md#run-lifecycle) as
`core.run_lifecycle`, and of the retry backoff of
[Job queue](/architecture/services/worker.md#job-queue) as `core.job_queue.next_attempt_at`."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from leadradar.core.enums import (
    JobStep,
    PipelineRunKind,
    PipelineRunStage,
    PipelineRunStatus,
    SourcePluginCode,
)
from leadradar.core.job_queue import next_attempt_at
from leadradar.core.run_lifecycle import (
    owed_final_job,
    refresh_first_jobs,
    run_outcome,
    stage_after_claim,
)

pytestmark = pytest.mark.unit

_NOW = datetime(2026, 9, 26, 12, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    ("current", "step", "expected"),
    [
        (None, JobStep.FETCH, PipelineRunStage.FETCH),
        (None, JobStep.DISCOVER, PipelineRunStage.FETCH),
        (PipelineRunStage.FETCH, JobStep.PROCESS, PipelineRunStage.PROCESS),
        (PipelineRunStage.PROCESS, JobStep.SIGNAL, PipelineRunStage.TRIAGE),
        (None, JobStep.EVALUATE, PipelineRunStage.CLASSIFY),
        (PipelineRunStage.EVIDENCE, JobStep.SCORE, PipelineRunStage.SCORE),
        # A retried earlier job never moves the run back.
        (PipelineRunStage.PROCESS, JobStep.FETCH, PipelineRunStage.PROCESS),
        # A second `SIGNAL` batch does not undo the stage the first one reached.
        (PipelineRunStage.EVIDENCE, JobStep.SIGNAL, PipelineRunStage.EVIDENCE),
    ],
)
def test_stage_after_claim(
    current: PipelineRunStage | None, step: JobStep, expected: PipelineRunStage
) -> None:
    assert stage_after_claim(current, step) is expected


@pytest.mark.parametrize(
    ("kind", "steps", "expected"),
    [
        (PipelineRunKind.ACCOUNT_REFRESH, {JobStep.FETCH}, JobStep.SCORE),
        (PipelineRunKind.ACCOUNT_REFRESH, {JobStep.FETCH, JobStep.SCORE}, None),
        (PipelineRunKind.RECLASSIFY, {JobStep.SIGNAL}, JobStep.SCORE),
        (PipelineRunKind.RECLASSIFY, set(), JobStep.SCORE),
        (PipelineRunKind.RESCORE, {JobStep.SCORE}, None),
        (PipelineRunKind.DISCOVERY, {JobStep.DISCOVER}, None),
        (PipelineRunKind.EVALUATION, {JobStep.EVALUATE}, None),
    ],
)
def test_owed_final_job(kind: PipelineRunKind, steps: set[JobStep], expected: JobStep) -> None:
    assert owed_final_job(kind, steps) == expected


@pytest.mark.parametrize(
    ("final_stage_failed", "has_errors", "pending_budget", "expected"),
    [
        (False, False, 0, PipelineRunStatus.SUCCEEDED),
        (False, True, 0, PipelineRunStatus.PARTIAL),
        (False, False, 1, PipelineRunStatus.PARTIAL),
        (False, True, 3, PipelineRunStatus.PARTIAL),
        (True, True, 0, PipelineRunStatus.FAILED),
        (True, True, 2, PipelineRunStatus.FAILED),
    ],
)
def test_run_outcome(
    final_stage_failed: bool, has_errors: bool, pending_budget: int, expected: PipelineRunStatus
) -> None:
    assert (
        run_outcome(
            final_stage_failed=final_stage_failed,
            has_errors=has_errors,
            pending_budget=pending_budget,
        )
        is expected
    )


def test_refresh_first_jobs_is_one_fetch_per_available_plugin_in_plugin_order() -> None:
    assert refresh_first_jobs({SourcePluginCode.WEBSITE, SourcePluginCode.GDELT}) == [
        (JobStep.FETCH, {"plugin_code": "GDELT"}),
        (JobStep.FETCH, {"plugin_code": "WEBSITE"}),
    ]


def test_refresh_first_jobs_without_an_available_plugin_is_the_score_job() -> None:
    assert refresh_first_jobs(set()) == [(JobStep.SCORE, {})]


@pytest.mark.parametrize(
    ("attempts", "expected_delay_s"),
    [(1, 30), (2, 60)],
)
def test_next_attempt_at_backs_off_exponentially(attempts: int, expected_delay_s: int) -> None:
    assert next_attempt_at(
        attempts=attempts, max_attempts=3, backoff_s=30, now=_NOW
    ) == _NOW + timedelta(seconds=expected_delay_s)


@pytest.mark.parametrize("attempts", [3, 4])
def test_next_attempt_at_is_none_once_max_attempts_started(attempts: int) -> None:
    assert next_attempt_at(attempts=attempts, max_attempts=3, backoff_s=30, now=_NOW) is None
