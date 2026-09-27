"""Unit tests of [worker Job queue](/architecture/services/worker.md#job-queue)'s priority
table, as `core.job_queue.job_priority`."""

from __future__ import annotations

import pytest

from leadradar.core.enums import PipelineRunKind, PipelineRunTrigger
from leadradar.core.job_queue import UnknownJobPriority, job_priority

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    ("kind", "trigger", "priority"),
    [
        (PipelineRunKind.RESCORE, PipelineRunTrigger.FEEDBACK, 0),
        (PipelineRunKind.RESCORE, PipelineRunTrigger.OVERRIDE, 0),
        (PipelineRunKind.RESCORE, PipelineRunTrigger.ACCOUNT_CHANGE, 0),
        (PipelineRunKind.ACCOUNT_REFRESH, PipelineRunTrigger.USER, 1),
        (PipelineRunKind.RECLASSIFY, PipelineRunTrigger.QUESTION_CHANGE, 3),
        (PipelineRunKind.RESCORE, PipelineRunTrigger.SCORING_ACTIVATION, 3),
        (PipelineRunKind.ACCOUNT_REFRESH, PipelineRunTrigger.SCHEDULE, 5),
        (PipelineRunKind.DISCOVERY, PipelineRunTrigger.SCHEDULE, 7),
        (PipelineRunKind.EVALUATION, PipelineRunTrigger.SCHEDULE, 7),
    ],
)
def test_job_priority_of_every_row_of_the_table(
    kind: PipelineRunKind, trigger: PipelineRunTrigger, priority: int
) -> None:
    assert job_priority(kind, trigger) == priority


def test_raises_for_a_pair_the_table_does_not_list() -> None:
    with pytest.raises(UnknownJobPriority):
        job_priority(PipelineRunKind.ACCOUNT_REFRESH, PipelineRunTrigger.FEEDBACK)
